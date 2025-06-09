# -*- coding: utf-8 -*-
import os
import asyncio
import aiohttp
import time
import re
import logging
import random
from typing import Optional, Dict, Any

# ======================
#  إعداد الـ Logging
# ======================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('discord_bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ======================
#  ثوابت البوت
# ======================
CHANNEL_ID     = "1119327577291640852"
MODAY_UID      = "432610292342587392"
USER_MENTION   = "<@578790686757879830>"

token = os.getenv('token')
if not token:
    logger.error("Authentication token not found in environment variables")
    exit(1)


class DiscordSelfBot:
    def __init__(self, token: str):
        self.token      = token
        self.base_url   = "https://discord.com/api/v10"
        self.headers    = {
            "Authorization": token,
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0"
        }
        self.session: Optional[aiohttp.ClientSession] = None
        self.user_info: Optional[Dict[str, Any]]         = None
        self.running    = False

    # ------------
    #  بدء التشغيل
    # ------------
    async def start(self):
        self.session = aiohttp.ClientSession()
        try:
            await self.get_user_info()
            logger.info(f"Connected as {self.user_info['username']}")
            self.running = True

            await asyncio.gather(
                self.claim_check_loop(),
                self.message_monitor_loop()
            )

        finally:
            await self.session.close()

    # ------------------------
    #  جلب بيانات المستخدم الحالي
    # ------------------------
    async def get_user_info(self):
        async with self.session.get(f"{self.base_url}/users/@me", headers=self.headers) as resp:
            if resp.status == 200:
                self.user_info = await resp.json()
            else:
                text = await resp.text()
                raise Exception(f"get_user_info failed: {resp.status} {text}")

    # ------------------------
    #  جلب الرسائل الأخيرة مع المكونات (buttons)
    # ------------------------
    async def get_recent_messages(self, channel_id: str, limit: int = 10) -> list:
        url = f"{self.base_url}/channels/{channel_id}/messages?limit={limit}"
        async with self.session.get(url, headers=self.headers) as resp:
            if resp.status == 200:
                return await resp.json()
            else:
                logger.error(f"get_recent_messages failed: {resp.status}")
                return []

    # ------------------------
    #  إرسال رسالة
    # ------------------------
    async def send_message(self, channel_id: str, content: str) -> Optional[Dict[str, Any]]:
        await asyncio.sleep(random.uniform(1, 2))
        payload = {"content": content}
        async with self.session.post(
            f"{self.base_url}/channels/{channel_id}/messages",
            headers=self.headers,
            json=payload
        ) as resp:
            if resp.status in (200, 201):
                return await resp.json()
            elif resp.status == 429:
                retry = int(resp.headers.get("Retry-After", 5))
                await asyncio.sleep(retry + 1)
                return await self.send_message(channel_id, content)
            else:
                logger.error(f"send_message failed: {resp.status}")
                return None

    # ------------------------
    #  ضغط زر تفاعلي (button) أسفل الرسالة
    # ------------------------
    async def press_button(self, msg: Dict[str, Any], button: Dict[str, Any]) -> bool:
        """
        يرسل تفاعل من نوع 3 (Component Interaction) للضغط على زر.
        """
        guild_id = msg.get("guild_id")
        channel_id = msg["channel_id"]
        message_id = msg["id"]
        application_id = MODAY_UID
        custom_id = button.get("custom_id")
        if not custom_id or not guild_id:
            return False

        payload = {
            "type": 3,
            "guild_id": guild_id,
            "channel_id": channel_id,
            "message_id": message_id,
            "application_id": application_id,
            "data": {
                "component_type": 2,
                "custom_id": custom_id
            }
        }
        async with self.session.post(
            f"{self.base_url}/interactions",
            headers=self.headers,
            json=payload
        ) as resp:
            if resp.status in (200, 204):
                logger.info(f"Button pressed: {custom_id}")
                return True
            else:
                text = await resp.text()
                logger.error(f"press_button failed: {resp.status} {text}")
                return False

    # ------------------------
    #  منطق الـ $tu → $ql → $wa
    # ------------------------
    async def check_claim_and_execute(self):
        try:
            await self.send_message(CHANNEL_ID, "$tu")
            await asyncio.sleep(random.uniform(1.2, 3))

            msgs = await self.get_recent_messages(CHANNEL_ID, 10)
            reply = ""
            for m in msgs:
                if m.get("author", {}).get("id") == MODAY_UID:
                    reply = m.get("content", "")
                    break

            low = reply.lower()
            if "you can't claim" in low:
                await self.send_message(CHANNEL_ID, "$ql wl1")
                await asyncio.sleep(1)
                await self.send_message(CHANNEL_ID, "y")
            elif "you can claim" in low:
                await self.send_message(CHANNEL_ID, "$ql wl2")
                await asyncio.sleep(1)
                await self.send_message(CHANNEL_ID, "y")

            m = re.search(r"You have \*\*(\d+)\*\* rolls left", reply)
            rolls = int(m.group(1)) if m else 0
            for _ in range(rolls):
                await self.send_message(CHANNEL_ID, "$wa")
                await asyncio.sleep(random.uniform(1.15, 2.02))

        except Exception as e:
            logger.error(f"check_claim_and_execute error: {e}")

    # ------------------------
    #  مراقبة الرسائل والتفاعل مع الأزرار
    # ------------------------
    async def handle_moday_message(self, msg: Dict[str, Any]):
        content = msg.get("content", "")
        # شرط التشغيل: Belongs to ce.l أو Wished by أو المنشن
        if not any(x in content for x in ("Belongs to ce.l", "Wished by", USER_MENTION)):
            return

        components = msg.get("components", [])
        # نمر على الصفوف (action rows)
        for row in components:
            for comp in row.get("components", []):
                # فقط الزرّات (type == 2)
                if comp.get("type") == 2:
                    await self.press_button(msg, comp)
                    return

    async def message_monitor_loop(self):
        last_id = None
        while self.running:
            msgs = await self.get_recent_messages(CHANNEL_ID, 15)
            for m in reversed(msgs):
                if m["id"] == last_id:
                    break
                if m.get("author", {}).get("id") == MODAY_UID:
                    await self.handle_moday_message(m)
            if msgs:
                last_id = msgs[0]["id"]
            await asyncio.sleep(8)

    async def claim_check_loop(self):
        await asyncio.sleep(random.uniform(5, 15))
        while self.running:
            await self.check_claim_and_execute()
            await asyncio.sleep(3600 + random.uniform(-100, 100))


# ======================
#  تشغيل البوت
# ======================
async def main():
    bot = DiscordSelfBot(token)
    await bot.start()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
