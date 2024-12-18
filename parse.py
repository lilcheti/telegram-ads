import re
import requests
from typing import List, Dict, Union
import logging
from dataclasses import dataclass
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class Config:
    target: str = "channel"  # bot or channel
    hash: str = ""
    cookie: str = ""
    owner_id: str = ""
    batch_size: int = 100
    rate_limit_delay: float = 0  # Delay between API calls in seconds
    pattern: str = r'\d+-([^">]+)'
    #ads
    title: str = ""
    text: str = ""
    promote_url: str = ""
    ad_info: str = ""

class TelegramAdManager:
    def __init__(self, config: Config):
        self.config = config
        self.headers = {
            "accept": "application/json, text/javascript, */*; q=0.01",
            "accept-language": "en-US,en;q=0.9",
            "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
            "cookie": config.cookie,
            "origin": "https://ads.telegram.org",
            "referer": "https://ads.telegram.org/account/ad/new",
            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        }

    def extract_telegram_usernames(self, html_content: str) -> List[str]:
        """Extract valid Telegram usernames from HTML content."""
        pattern = self.config.pattern
        matches = re.findall(pattern, html_content)
        return [match for match in matches if not any(char in match for char in ".\\ =@#$%^&*()+-~/\"`'[]{}|,<>!?:;")]

    def search_channel(self, username: str) -> Dict:
        """Search for a channel/bot by username."""
        url = f"https://ads.telegram.org/api?hash={self.config.hash}"
        
        data = {
            "query": f"@{username}",
            "field": f"{self.config.target}s",
            "method": f"search{self.config.target.capitalize()}"
        }

        try:
            response = requests.post(url, headers=self.headers, data=data)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Error searching for {username}: {str(e)}")
            return {"ok": False, "error": str(e)}

    def create_ad(self, channel_ids: str, batch_no: int) -> Dict:
        """Create an ad draft with specified channel IDs."""
        url = f"https://ads.telegram.org/api?hash={self.config.hash}"
        
        data = {
            "owner_id": self.config.owner_id,
            "title": self.config.title + " " + str(int(batch_no/100+1)),
            "text": self.config.text,
            "promote_url": self.config.promote_url,
            "website_name": "",
            "website_photo": "",
            "media": "",
            "ad_info": self.config.ad_info,
            "cpm": "0.1",
            "views_per_user": "1",
            "budget": "0.1",
            "daily_budget": "0",
            "active": "1",
            "target_type": self.config.target+"s",
            "langs": "",
            "topics": "",
            "exclude_topics": "",
            "exclude_channels": "",
            "method": "createAd" #or "saveAdDraft"
        }

        # Add channels or bots based on target type
        if self.config.target == "channel":
            data["channels"] = channel_ids
        else:
            data["bots"] = channel_ids

        try:
            response = requests.post(url, headers=self.headers, data=data)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Error creating ad: {str(e)}")
            return {"ok": False, "error": str(e)}

    def process_usernames(self, usernames: List[str]) -> List[str]:
        """Process usernames and return channel IDs."""
        channel_ids = []
        
        for username in usernames:
            response = self.search_channel(username)
            
            if response.get("ok") == False:
                logger.warning(f"Failed to process username {username}: {response.get('error', 'Unknown error')}")
                continue
                
            if self.config.target in response:
                channel_ids.append(response[self.config.target]["id"])
            else:
                logger.warning(f"Invalid response format for username {username}")
            
            time.sleep(self.config.rate_limit_delay)  # Rate limiting
            
        return channel_ids

    def process_in_batches(self, html_file_path: str) -> None:
        """Process channels in batches and create ads."""
        # Read and extract usernames
        with open(html_file_path, "r", encoding="utf-8") as file:
            content = file.read()
        
        usernames = self.extract_telegram_usernames(content)
        logger.info(f"Usernames Found: {len(usernames)}")
        channel_ids = self.process_usernames(usernames)
        
        # Process in batches
        for i in range(0, len(channel_ids), self.config.batch_size):
            batch = channel_ids[i:i + self.config.batch_size]
            batch_str = ";".join(map(str, batch))
            
            logger.info(f"Processing batch {i//self.config.batch_size + 1} "
                       f"({len(batch)} channels)")
            
            # if i > 0:
            #     proceed = input(f"Do you want to create an ad for the next {len(batch)} "
            #                   f"channels? (y/n): ").lower()
            #     if proceed != 'y':
            #         logger.info("Batch processing stopped by user")
            #         break
            
            response = self.create_ad(batch_str, i)
            
            if response.get("ok"):
                logger.info(f"Successfully created ad for batch "
                          f"{i//self.config.batch_size + 1}")
            else:
                logger.error(f"Failed to create ad for batch "
                           f"{i//self.config.batch_size + 1}: "
                           f"{response.get('error', 'Unknown error')}")
            
            time.sleep(self.config.rate_limit_delay)

def main():
    # Initialize configuration
    config = Config()
    
    # Create ad manager instance
    ad_manager = TelegramAdManager(config)
    
    # Process the file
    html_file_path = "tgstat.html"
    try:
        ad_manager.process_in_batches(html_file_path)
    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")

if __name__ == "__main__":
    main()
