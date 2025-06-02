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

# Emoji codes for loot and gems
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

    def extract_character_name(self, message_content: str) -> Optional[str]:
        """Extract character name from role-playing message with improved patterns"""
        try:
            patterns = [
                r'\*\*([^*]+)\*\*',  # text between double asterisks
                r'`([^`]+)`',        # text between backticks
                r'"([^"]+)"',        # text between double quotes
                r"'([^']+)'",        # text between single quotes
                r'【([^】]+)】',       # text between Japanese brackets
                r'《([^》]+)》',       # text between Chinese brackets
                r'〖([^〗]+)〗',       # text between other brackets
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, message_content)
                if matches:
                    for match in matches:
                        clean_match = match.strip()
                        if len(clean_match) > 2 and not clean_match.isdigit() and not clean_match.startswith('$'):
                            return clean_match
            
            return None
        except Exception as e:
            logger.error(f"Error extracting character name: {e}")
            return None

    async def log_collected_character(self, character_name: str):
        """Log collected character to a file"""
        try:
            with open("collected_characters.txt", "a", encoding="utf-8") as f:
                timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                f.write(f"[{timestamp}] {character_name}\n")
            
            try:
                with open("collected_characters.txt", "r", encoding="utf-8") as f:
                    lines = f.readlines()
                    character_count = len([line for line in lines if line.strip() and not line.startswith('#')])
                    logger.info(f"Total collected characters: {character_count}")
            except:
                pass
                
        except Exception as e:
            logger.error(f"Error logging character: {e}")

    async def check_claim_and_execute(self):
        """Check for claim availability and execute appropriate commands"""
        try:
            logger.info("Starting claim check...")
            
            response = await self.send_message(CHANNEL_ID, "$tu")
            if not response:
                logger.error("Failed to send '$tu' command")
                return
            
            await asyncio.sleep(random.uniform(1.2, 3))
            
            recent_messages = await self.get_recent_messages(CHANNEL_ID, 10)
            
            moday_response = None
            for message in recent_messages:
                author = message.get("author", {})
                if author.get("id") == MODAY_UID or "Mudae#0807" in author.get("username", ""):
                    content = message.get("content", "")
                    lower_content = content.lower()
                    if any(keyword in lower_content for keyword in ["claim", "you have", "you may", "can't react", "power", "stock"]):
                        moday_response = content
                        logger.info(f"MoDay response found: {content[:100]}...")
                        break
            
            if not moday_response:
                logger.warning("No clear MoDay response after '$tu'")
                return
            
            # Extract rolls left
            rolls_left = 0
            rolls_match = re.search(r"You have \*\*(\d+)\*\* rolls left", moday_response)
            if rolls_match:
                rolls_left = int(rolls_match.group(1))
                logger.info(f"Rolls left: {rolls_left}")
            
            # Decide which command to send
            # lower_moday = moday_response.lower()
            # if any(keyword in lower_moday for keyword in ["can't claim", "wait"]):
            #     logger.info("Cannot claim – sending '$ql wl'")
            #     await self.send_message(CHANNEL_ID, "$ql wl")
            # else:
            #     logger.info("Can claim – sending '$ql wl2'")
            #     await self.send_message(CHANNEL_ID, "$ql wl2")
            
            # await asyncio.sleep(random.uniform(1, 3))
            # await self.send_message(CHANNEL_ID, "y")
            
            # Auto-roll commands if rolls remain
            if rolls_left > 0:
                logger.info(f"Sending {rolls_left} '$wa' commands with random delays (2-3 seconds)")
                for i in range(rolls_left):
                    await self.send_message(CHANNEL_ID, "$wa")
                    wait_time = random.uniform(1.15, 2.02)
                    await asyncio.sleep(wait_time)
            
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
        """Process messages from MoDay bot"""
        try:
            content = message_data.get("content", "")
            message_id = message_data.get("id")
            
            found_loot = False
            for emoji, loot_type in LOOT_EMOJIS.items():
                if emoji in content:
                    logger.info(f"Found loot: {loot_type}")
                    success = await self.add_reaction(CHANNEL_ID, message_id, emoji)
                    if success:
                        found_loot = True
                        await asyncio.sleep(random.uniform(0.3, 0.8))
            
            user_mention = f"<@{self.user_info['id']}>"
            username = self.user_info["username"]
            
            if user_mention in content or username in content:
                if any(keyword in content.lower() for keyword in ["claims", "rolled", "appears"]):
                    character_name = self.extract_character_name(content)
                    if character_name:
                        await self.log_collected_character(character_name)
                        logger.info(f"Collected character: {character_name}")
            
            if found_loot:
                logger.info("Loot was found in this message")
                    
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
                
                next_check = 3600 + random.uniform(-100, 100)
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
