# -*- coding: utf-8 -*-
# Import required libraries
import os
import asyncio
import aiohttp
import json
import time
import re
import logging
import random
from typing import Optional, Dict, Any

# Configure logging to handle errors
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('discord_bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# The specific channel ID to interact with MoDay bot
CHANNEL_ID = "1119327577291640852"
# The unique ID of the MoDay bot
MODAY_UID = "432610292342587392"

# Get the authentication token from environment variables
token = os.getenv('token')
if not token:
    logger.error("Authentication token not found in environment variables")
    exit(1)

# Emoji codes for loot and gems (you can still use this to catch loot)
LOOT_EMOJIS = {
    '💎': 'gem_blue',
    '💛': 'gem_yellow',
    '🤍': 'gem_white',
    '🧡': 'gem_orange',
    '🟡': 'kakera_yellow',
    '⚪': 'kakera_white',
    '🟠': 'kakera_orange',
    '🔶': 'kakera_orange_diamond',
    '💰': 'treasure',
    '🏆': 'trophy'
}

class DiscordSelfBot:
    def __init__(self, token: str):
        self.token = token
        self.base_url = "https://discord.com/api/v10"
        self.headers = {
            "Authorization": token,
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        self.session: Optional[aiohttp.ClientSession] = None
        self.user_info: Optional[Dict[str, Any]] = None
        self.running = False

    async def start(self):
        """Start the bot"""
        self.session = aiohttp.ClientSession()
        try:
            await self.get_user_info()
            logger.info(f"Connected as {self.user_info['username']}")
            print(f"Connected as {self.user_info['username']}")

            self.running = True

            await asyncio.gather(
                self.claim_check_loop(),
                self.message_monitor_loop()
            )

        except Exception as e:
            logger.error(f"Error starting the bot: {e}")
        finally:
            if self.session:
                await self.session.close()

    async def get_user_info(self):
        """Get current user information"""
        async with self.session.get(f"{self.base_url}/users/@me", headers=self.headers) as response:
            if response.status == 200:
                self.user_info = await response.json()
            else:
                error_text = await response.text()
                raise Exception(f"Failed to get user info: {response.status} - {error_text}")

    async def get_recent_messages(self, channel_id: str, limit: int = 10) -> list:
        """Retrieve recent messages from a channel"""
        try:
            url = f"{self.base_url}/channels/{channel_id}/messages?limit={limit}"
            async with self.session.get(url, headers=self.headers) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.error(f"Failed to fetch messages: {response.status}")
                    return []
        except Exception as e:
            logger.error(f"Error fetching messages: {e}")
            return []

    async def send_message(self, channel_id: str, content: str):
        """Send a message with random delay and rate-limit handling"""
        try:
            delay = random.uniform(1.0, 2.0)
            await asyncio.sleep(delay)

            payload = {"content": content}
            async with self.session.post(
                f"{self.base_url}/channels/{channel_id}/messages",
                headers=self.headers,
                json=payload
            ) as response:
                if response.status in [200, 201]:
                    data = await response.json()
                    logger.info(f"Message sent: {content}")
                    return data
                elif response.status == 429:
                    retry_after = int(response.headers.get('Retry-After', 5))
                    logger.warning(f"Rate limited, waiting {retry_after} seconds")
                    await asyncio.sleep(retry_after + random.uniform(1, 3))
                    return await self.send_message(channel_id, content)
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to send message: {response.status} - {error_text}")
                    return None
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            return None

    async def add_reaction(self, channel_id: str, message_id: str, emoji: str):
        """Add a reaction to a message"""
        try:
            import urllib.parse
            emoji_encoded = urllib.parse.quote(emoji)

            url = f"{self.base_url}/channels/{channel_id}/messages/{message_id}/reactions/{emoji_encoded}/@me"
            async with self.session.put(url, headers=self.headers) as response:
                if response.status == 204:
                    logger.info(f"Reaction added: {emoji}")
                    return True
                elif response.status == 429:
                    retry_after = int(response.headers.get('Retry-After', 1))
                    await asyncio.sleep(retry_after + random.uniform(0.5, 1.5))
                    return await self.add_reaction(channel_id, message_id, emoji)
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to add reaction: {response.status} - {error_text}")
                    return False
        except Exception as e:
            logger.error(f"Error adding reaction: {e}")
            return False

    async def check_claim_and_execute(self):
        """Check for claim availability and execute appropriate commands"""
        try:
            logger.info("Starting claim check...")

            # 1) Send $tu and wait
            response = await self.send_message(CHANNEL_ID, "$tu")
            if not response:
                logger.error("Failed to send '$tu' command")
                return

            await asyncio.sleep(random.uniform(1.2, 3))
            recent = await self.get_recent_messages(CHANNEL_ID, 10)

            # 2) Find the first MoDay reply
            moday_msg = None
            for msg in recent:
                author = msg.get("author", {})
                if author.get("id") == MODAY_UID:
                    moday_msg = msg.get("content", "")
                    break

            if not moday_msg:
                logger.warning("No MoDay reply found for '$tu'")
                return

            lower = moday_msg.lower()
            # 3) Resend $ql wl1 or $ql wl2 based on response, then send "y"
            if "you can't claim" in lower:
                logger.info("Detected no-claim → sending '$ql wl1'")
                await self.send_message(CHANNEL_ID, "$ql wl1")
                await asyncio.sleep(random.uniform(0.8, 1.5))
                logger.info("Confirming with 'y'")
                await self.send_message(CHANNEL_ID, "y")

            else:
                logger.info("Detected can-claim → sending '$ql wl2'")
                await self.send_message(CHANNEL_ID, "$ql wl2")
                await asyncio.sleep(random.uniform(0.8, 1.5))
                logger.info("Confirming with 'y'")
                await self.send_message(CHANNEL_ID, "y")

            
            # 4) Auto-roll remaining rolls
            rolls_left = 0
            m = re.search(r"You have \*\*(\d+)\*\* rolls left", moday_msg)
            if m:
                rolls_left = int(m.group(1))
                logger.info(f"Rolls left: {rolls_left}")

            for _ in range(rolls_left):
                await self.send_message(CHANNEL_ID, "$wa")
                await asyncio.sleep(random.uniform(1.15, 2.02))

        except Exception as e:
            logger.error(f"Error during claim check: {e}")

        

    async def message_monitor_loop(self):
        """Monitor incoming messages to look for loot and characters"""
        last_message_id = None

        while self.running:
            try:
                messages = await self.get_recent_messages(CHANNEL_ID, 15)

                for message in reversed(messages):
                    message_id = message.get("id")

                    if last_message_id and message_id == last_message_id:
                        break

                    author = message.get("author", {})
                    if author.get("id") == self.user_info["id"]:
                        continue

                    if author.get("id") == MODAY_UID or "MoDay" in author.get("username", ""):
                        await self.handle_moday_message(message)
                        await asyncio.sleep(random.uniform(0.5, 1.5))

                if messages:
                    last_message_id = messages[0].get("id")

                await asyncio.sleep(random.uniform(8, 15))

            except Exception as e:
                logger.error(f"Error in message monitoring loop: {e}")
                await asyncio.sleep(random.uniform(30, 60))

    async def handle_moday_message(self, message_data: Dict[str, Any]):
        """Process messages from MoDay bot, auto-clicking the first reaction-button"""
        try:
            content = message_data.get("content", "")
            message_id = message_data.get("id")

            # Trigger only if contains the required text or mention
            trigger = ("Belongs to ce.l" in content) or ("<@578790686757879830>" in content)
            if not trigger:
                return

            reactions = message_data.get("reactions", [])
            if not reactions:
                return

            # Take the first reaction button provided by the bot
            emoji = reactions[0]["emoji"]
            if emoji.get("id"):
                emoji_str = f"{emoji['name']}:{emoji['id']}"
            else:
                emoji_str = emoji["name"]

            success = await self.add_reaction(CHANNEL_ID, message_id, emoji_str)
            if success:
                logger.info(f"Clicked reaction-button {emoji_str} on MoDay embed")

        except Exception as e:
            logger.error(f"Error handling MoDay message: {e}")

    async def claim_check_loop(self):
        """Scheduled claim-check loop every hour"""
        initial_delay = random.uniform(10, 30)
        logger.info(f"Waiting {initial_delay:.1f} seconds before starting claim checks")
        await asyncio.sleep(initial_delay)

        while self.running:
            try:
                logger.info("Running scheduled claim check...")
                await self.check_claim_and_execute()

                next_check = 3600 + random.uniform(-150, 50)
                logger.info(f"Next claim check in {next_check/60:.1f} minutes")
                await asyncio.sleep(next_check)

            except Exception as e:
                logger.error(f"Error in scheduled claim-check loop: {e}")
                await asyncio.sleep(random.uniform(300, 600))


# Run the bot
async def main():
    bot = DiscordSelfBot(token)
    try:
        await bot.start()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
        bot.running = False
    except Exception as e:
        logger.error(f"Error running the bot: {e}")

if __name__ == "__main__":
    try:
        logger.info("Starting enhanced bot...")
        asyncio.run(main())
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
