import os
import asyncio
import json
import random
import time
from typing import List

from scraper.platform_controller import PlatformScrapeController
from scraper.selenium_twitter_scraper import SeleniumTwitterScraper

class TwitterScrapeController(PlatformScrapeController):
    """
    Controller for Twitter profile discovery and image scraping.
    """
    
    def __init__(
        self, 
        profiles_file: str = "data/twitter_profiles.json", 
        output_dir: str = "data/downloaded_images/twitter"
    ):
        """
        Initialize the Twitter scrape controller.
        
        Args:
            profiles_file (str): Path to store discovered profiles
            output_dir (str): Directory to save downloaded images
        """
        super().__init__(
            platform_name="Twitter", 
            profiles_file=profiles_file, 
            output_dir=output_dir
        )
        
        # Predefined search terms to find profiles
        self.profile_search_queries = [
            'photographer', 
            'portrait', 
            'selfie', 
            'people', 
            'face', 
            'headshot', 
            'human'
        ]
    
    async def find_profiles(
        self, 
        target_count: int = 200, 
        max_runtime_minutes: int = 30
    ) -> List[str]:
        """
        Find Twitter profiles using search queries.
        
        Args:
            target_count (int): Number of profiles to find
            max_runtime_minutes (int): Maximum runtime for discovery
        
        Returns:
            List[str]: List of discovered profile handles
        """
        self.logger.info(f"Discovering Twitter profiles (target: {target_count})")
        
        # Use predefined or previously discovered profiles
        discovered_profiles = set(self._load_profiles())
        
        # Simulate profile discovery by extracting usernames from search
        for query in random.sample(self.profile_search_queries, len(self.profile_search_queries)):
            if len(discovered_profiles) >= target_count:
                break
            
            # Simulate finding new profiles (in a real implementation, 
            # you'd use Twitter's search or a third-party API)
            try:
                # Simulated profile generation 
                # In a real scenario, this would be replaced with actual profile discovery
                generated_profiles = [
                    f"{query}_{random.randint(1, 1000)}" 
                    for _ in range(random.randint(5, 20))
                ]
                
                # Add to discovered profiles
                discovered_profiles.update(generated_profiles)
            except Exception as e:
                self.logger.error(f"Error discovering profiles for query '{query}': {e}")
        
        # Trim to target count
        discovered_profiles = list(discovered_profiles)[:target_count]
        
        self.logger.info(f"Discovered {len(discovered_profiles)} Twitter profiles")
        return discovered_profiles
    
    async def scrape_images(
        self, 
        max_profiles: int = 5, 
        max_images_per_profile: int = 10
    ) -> List[str]:
        """
        Scrape images from discovered Twitter profiles.
        
        Args:
            max_profiles (int): Maximum number of profiles to scrape
            max_images_per_profile (int): Maximum images to download per profile
        
        Returns:
            List[str]: Paths to downloaded images
        """
        self.logger.info(f"Scraping images from {max_profiles} Twitter profiles")
        
        # Ensure we have profiles to scrape
        if not self.profiles:
            self.profiles = self._load_profiles()
        
        # Create Twitter scraper
        scraper = SeleniumTwitterScraper(
            output_dir=self.output_dir,
            profiles_file=self.profiles_file
        )
        
        # Scrape images
        images = scraper.run(
            max_profiles=max_profiles, 
            max_images_per_profile=max_images_per_profile
        )
        
        self.logger.info(f"Downloaded {len(images)} images from Twitter")
        return images

# Convenience function for easy usage
async def scrape_twitter_profiles(
    profile_count: int = 200, 
    max_profiles_to_scrape: int = 5, 
    max_images_per_profile: int = 10
) -> dict:
    """
    Convenience function to run the full Twitter scraping pipeline.
    
    Args:
        profile_count (int): Number of profiles to discover
        max_profiles_to_scrape (int): Maximum profiles to scrape
        max_images_per_profile (int): Maximum images to download per profile
    
    Returns:
        dict: Scraping process statistics
    """
    controller = TwitterScrapeController()
    return await controller.run_full_pipeline(
        profile_count=profile_count,
        max_profiles_to_scrape=max_profiles_to_scrape,
        max_images_per_profile=max_images_per_profile
    )

# For command-line usage
def main():
    import asyncio
    import logging
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Run the scraper
    results = asyncio.run(scrape_twitter_profiles())
    print(json.dumps(results, indent=2))

if __name__ == "__main__":
    main()