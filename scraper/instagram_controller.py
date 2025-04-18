import os
import asyncio
import json
import random
import time
from typing import List

from scraper.platform_controller import PlatformScrapeController
from scraper.instagram_profile_finder import InstagramProfileFinder
from scraper.selenium_instagram_scraper import SeleniumInstagramScraper

class InstagramScrapeController(PlatformScrapeController):
    """
    Controller for Instagram profile discovery and image scraping.
    Follows the PlatformScrapeController base class pattern.
    """
    
    def __init__(
        self, 
        profiles_file: str = "data/instagram_profiles.json", 
        output_dir: str = "data/downloaded_images/instagram"
    ):
        """
        Initialize the Instagram scrape controller.
        
        Args:
            profiles_file (str): Path to store discovered profiles
            output_dir (str): Directory to save downloaded images
        """
        super().__init__(
            platform_name="Instagram", 
            profiles_file=profiles_file, 
            output_dir=output_dir
        )
    
    async def find_profiles(
        self, 
        target_count: int = 200, 
        max_runtime_minutes: int = 30
    ) -> List[str]:
        """
        Find Instagram profiles using InstagramProfileFinder.
        
        Args:
            target_count (int): Number of profiles to find
            max_runtime_minutes (int): Maximum runtime for discovery
        
        Returns:
            List[str]: List of discovered profile handles
        """
        self.logger.info(f"Discovering Instagram profiles (target: {target_count})")
        
        # Use InstagramProfileFinder to discover profiles
        finder = InstagramProfileFinder(output_file=self.profiles_file)
        profiles = await finder.run(
            target_count=target_count, 
            max_runtime_minutes=max_runtime_minutes
        )
        
        self.logger.info(f"Discovered {len(profiles)} Instagram profiles")
        return profiles
    
    async def scrape_images(
        self, 
        max_profiles: int = 5, 
        max_images_per_profile: int = 10
    ) -> List[str]:
        """
        Scrape images from discovered Instagram profiles.
        
        Args:
            max_profiles (int): Maximum number of profiles to scrape
            max_images_per_profile (int): Maximum images to download per profile
        
        Returns:
            List[str]: Paths to downloaded images
        """
        self.logger.info(f"Scraping images from {max_profiles} Instagram profiles")
        
        # Ensure we have profiles to scrape
        if not self.profiles:
            self.profiles = self._load_profiles()
        
        # Create Instagram scraper
        scraper = SeleniumInstagramScraper(
            output_dir=self.output_dir,
            profiles_file=self.profiles_file
        )
        
        # Scrape images
        images = scraper.run(
            max_profiles=max_profiles, 
            max_images_per_profile=max_images_per_profile
        )
        
        self.logger.info(f"Downloaded {len(images)} images from Instagram")
        return images

# Convenience function for easy usage
async def scrape_instagram_profiles(
    profile_count: int = 200, 
    max_profiles_to_scrape: int = 5, 
    max_images_per_profile: int = 10
) -> dict:
    """
    Convenience function to run the full Instagram scraping pipeline.
    
    Args:
        profile_count (int): Number of profiles to discover
        max_profiles_to_scrape (int): Maximum profiles to scrape
        max_images_per_profile (int): Maximum images to download per profile
    
    Returns:
        dict: Scraping process statistics
    """
    controller = InstagramScrapeController()
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
    results = asyncio.run(scrape_instagram_profiles())
    print(json.dumps(results, indent=2))

if __name__ == "__main__":
    main()