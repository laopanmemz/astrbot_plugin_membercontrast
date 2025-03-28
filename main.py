import json
import os
import aiohttp
from astrbot.api import logger
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.core.platform.sources.gewechat.gewechat_event import GewechatPlatformEvent

@register("astrbot_plugin_membercontrast", "laopanmemz", "微信群组群员历史对比", "1.0.0")
class Watcher(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.member_cache = {} # 创建缓存字典

    # 构造请求群员列表方法
    async def post_members(self, event: AstrMessageEvent):
        assert isinstance(event, GewechatPlatformEvent)
        try:
            payloads = {
                "appId": event.client.appid,
                "chatroomId": event.get_group_id(),
            }
            headers = {
                "X-GEWE-TOKEN": event.client.token,
                "Content-Type": "application/json"
            }
            gewe_url = event.client.base_url + "/group/getChatroomMemberList"

            async with aiohttp.ClientSession() as session:
                async with session.post(gewe_url, headers=headers, json=payloads) as resp:
                    if resp.status != 200:
                        logger.error(f"❌获取成员列表失败，状态码: {resp.status}")
                        return []
                    data = await resp.json()
                    members = data.get("data", {}).get("memberList", [])
                    return {m["wxid"]: m["nickname"] for m in members}

        except Exception as e:
            logger.error(f"❌获取成员列表失败: {e}")
            return []

    # 加载缓存群员列表，如果缓存为空则使用请求方法获取列表
    async def load_members(self):
        with open(os.path.join("data","plugins","astrbot_plugin_membercontrast","member_cache.json"), "r", encoding='utf-8-sig') as f:
            self.member_cache = json.load(f)
            if len(self.member_cache) == 0:
                logger.info("⌛加载成员列表为空，开始获取成员列表")
                self.member_cache = await self.post_members()
                with open(os.path.join("data","plugins","astrbot_plugin_membercontrast","member_cache.json"), "w", encoding='utf-8-sig') as f:
                    json.dump(self.member_cache, f, indent=2, ensure_ascii=False)

            return self.member_cache
    # 注册指令的装饰器。指令名为 对比成员。注册成功后，发送 `/对比成员` 就会触发这个指令`
    @filter.command("对比成员")
    async def start(self, event: AstrMessageEvent):
        if event.get_platform_name() == "gewechat": # 判断是否为微信
            last_member = await self.load_members() # 获取缓存的成员列表
            member_data = await self.post_members(event) # 获取最新的成员列表
            if member_data == last_member: # 如果缓存的成员列表和最新的成员列表相同，则发送提示消息
                yield event.plain_result("🕘群成员暂无变化")
            else:
                last_keys = set(last_member.keys()) # 获取缓存的成员列表的键
                exceed_keys = set(member_data.keys()) # 获取最新的成员列表的键

                remove_member = last_keys - exceed_keys # 获取减少的成员列表
                add_member = exceed_keys - last_keys # 获取新增的成员列表

                removed_nicknames = [last_member[k] for k in remove_member] # 获取减少的成员列表的昵称
                added_nicknames = [member_data[k] for k in add_member] # 获取新增的成员列表的昵称

                if removed_nicknames: # 如果有减少的成员，则发送提示消息
                    yield event.plain_result(f"⚠侦测到以下成员退群: {', '.join(removed_nicknames)}")
                if added_nicknames: # 如果有新增的成员，则发送提示消息
                    yield event.plain_result(f"🎉有新成员入群：{', '.join(added_nicknames)}")
                if removed_nicknames or added_nicknames: # 如果有变化，就把最新的成员列表覆盖进member_cache.json
                    with open(os.path.join("data","plugins","astrbot_plugin_membercontrast","member_cache.json"), "w", encoding='utf-8-sig') as f:
                        json.dump(member_data, f, indent=2, ensure_ascii=False)
                        logger.info("✅成功更新缓存成员列表！")

        if event.get_platform_name() == "aiocqhttp":
            yield event.plain_result("\n⚠检测功能仅支持微信......\nQQ都有 退群通知 和 Q群管家入群欢迎功能 了，你还要这个干啥？（（大雾")
            event.stop_event()
            return
        if event.get_platform_name() != "gewechat" or event.get_platform_name() != "aiocqhttp":
            yield event.plain_result("\n⚠检测功能仅支持微信......")
            event.stop_event()
            return 