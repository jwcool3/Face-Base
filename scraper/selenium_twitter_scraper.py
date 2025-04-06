import os
import time
import random
import json
import asyncio
import urllib.request
from typing import List, Dict

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, 
    NoSuchElementException, 
    WebDriverException
)

from utils.logger import get_logger

class SeleniumTwitterScraper:
    """
    Selenium-based scraper for collecting public images from Twitter.
    """
    
    def __init__(
        self, 
        output_dir: str = "data/downloaded_images/twitter", 
        profiles_file: str = "data/twitter_profiles.json"
    ):
        """
        Initialize the Twitter image scraper.
        
        Args:
            output_dir (str): Directory to save downloaded images.
            profiles_file (str): File to store discovered profiles.
        """
        self.logger = get_logger(__name__)
        
        # Ensure output directory exists
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Profiles file
        self.profiles_file = profiles_file
        
        # User agent rotation to reduce detection
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36'
        ]
        
        # Search queries for finding people images
        self.search_queries = [
            'portrait', 
            'selfie', 
            'people', 
            'face', 
            'headshot', 
            'human', 
            'person'
        ]
    
    def _setup_driver(self) -> webdriver.Chrome:
        """
        Setup and configure Chrome WebDriver with appropriate options.
        
        Returns:
            webdriver.Chrome: Configured Chrome WebDriver
        """
        chrome_options = Options()
        
        # Randomize user agent
        user_agent = random.choice(self.user_agents)
        chrome_options.add_argument(f'user-agent={user_agent}')
        
        # Other helpful options
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--disable-extensions')
        chrome_options.add_argument('--start-maximized')
        
        # Always run in headless mode to prevent browser window
        chrome_options.add_argument('--headless')
        
        # Additional privacy/anti-detection options
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # Bypass some common detection methods
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--disable-notifications')
        
        # Create the webdriver
        driver = webdriver.Chrome(options=chrome_options)
        
        # Additional stealth techniques
        try:
            from selenium_stealth import stealth
            stealth(driver,
                languages=["en-US", "en"],
                vendor="Google Inc.",
                platform="Win32",
                webgl_vendor="Intel Inc.",
                renderer="Intel Iris OpenGL Engine",
                fix_hairline=True,
            )
        except ImportError:
            self.logger.warning("selenium-stealth not installed. Some anti-bot measures might not be bypassed.")
        
        # Set implicit wait and page load timeout
        driver.implicitly_wait(10)
        driver.set_page_load_timeout(30)
        
        return driver
    
    def _get_image_urls(self, driver, max_scroll: int = 5) -> List[str]:
        """
        Extract image URLs from the current page.
        
        Args:
            driver (webdriver.Chrome): Selenium WebDriver
            max_scroll (int): Maximum number of scroll downs to perform.
        
        Returns:
            List[str]: Collected image URLs
        """
        image_urls = set()
        
        try:
            # Initial wait for page load
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.TAG_NAME, 'body'))
            )
            
            # Scroll and collect images
            last_height = driver.execute_script("return document.body.scrollHeight")
            scroll_count = 0
            
            while scroll_count < max_scroll:
                # Scroll down
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                
                # Wait for content to load
                time.sleep(random.uniform(2, 3))
                
                # Look for images
                try:
                    # Try multiple selectors for images
                    selectors = [
                        'img[src*="media"]',  # Twitter media images
                        'div[data-testid="tweetPhoto"] img',  # Tweet photos
                        'div[aria-label="Image"] img',  # Image containers
                        'img[alt*="Image"]'  # Images with alt text
                    ]
                    
                    for selector in selectors:
                        elements = driver.find_elements(By.CSS_SELECTOR, selector)
                        for img in elements:
                            src = img.get_attribute('src')
                            if src and src.startswith('http') and not any(x in src.lower() for x in [
                                'emoji', 'avatar', 'profile', 'logo', 'icon'
                            ]):
                                # Get highest quality version of the image
                                src = src.replace('&name=small', '&name=large')
                                src = src.replace('&name=medium', '&name=large')
                                image_urls.add(src)
                
                except Exception as e:
                    self.logger.warning(f"Error finding images on scroll {scroll_count}: {e}")
                
                # Check if we've reached the bottom
                new_height = driver.execute_script("return document.body.scrollHeight")
                if new_height == last_height:
                    # Try one more time with a longer wait
                    time.sleep(2)
                    new_height = driver.execute_script("return document.body.scrollHeight")
                    if new_height == last_height:
                        break
                
                last_height = new_height
                scroll_count += 1
                
                # Random delay between scrolls
                time.sleep(random.uniform(1, 2))
        
        except TimeoutException:
            self.logger.error("Timeout waiting for page to load")
        except WebDriverException as e:
            self.logger.error(f"WebDriver error: {e}")
        except Exception as e:
            self.logger.error(f"Error extracting image URLs: {e}")
        
        return list(image_urls)
    
    def _download_image(self, url: str, query: str, index: int) -> str:
        """
        Download an image from a given URL.
        
        Args:
            url (str): Image URL to download
            query (str): Search query used to find the image
            index (int): Image index within the query results
        
        Returns:
            str: Path to downloaded image
        """
        # Create query-specific subdirectory
        query_dir = os.path.join(self.output_dir, query.replace(' ', '_'))
        os.makedirs(query_dir, exist_ok=True)
        
        # Generate filename
        filename = f"{query}_{index}_{int(time.time())}.jpg"
        filepath = os.path.join(query_dir, filename)
        
        # Use urllib to download
        headers = {
            'User-Agent': random.choice(self.user_agents),
            'Referer': 'https://twitter.com/'
        }
        
        # Create custom opener
        opener = urllib.request.build_opener()
        opener.addheaders = list(headers.items())
        urllib.request.install_opener(opener)
        
        # Download the image
        urllib.request.urlretrieve(url, filepath)
        
        return filepath
    
    def run(
        self, 
        max_profiles=5, 
        max_images_per_profile=10
    ) -> List[str]:
        """
        Run the Twitter scraper to download images.
        
        Args:
            max_profiles (int): Maximum number of searches/profile types
            max_images_per_profile (int): Maximum images per search query
        
        Returns:
            List[str]: Paths to downloaded images
        """
        self.logger.info(f"Starting Twitter scraping: {max_profiles} searches, {max_images_per_profile} images per search")
        
        # Track scraped images and statistics
        all_images = []
        profile_stats = {}
        
        # Setup webdriver
        driver = self._setup_driver()
        
        try:
            # Iterate through queries
            for query in random.sample(self.search_queries, min(max_profiles, len(self.search_queries))):
                try:
                    # Construct Twitter search URL
                    search_url = f"https://twitter.com/search?q={query}&src=typed_query&f=image"
                    driver.get(search_url)
                    
                    # Wait for page to load
                    time.sleep(random.uniform(2, 4))
                    
                    # Extract image URLs
                    image_urls = self._get_image_urls(driver)
                    
                    # Download images
                    profile_images = []
                    for i, url in enumerate(image_urls):
                        if len(profile_images) >= max_images_per_profile:
                            break
                        
                        try:
                            filepath = self._download_image(url, query, i)
                            profile_images.append(filepath)
                            all_images.append(filepath)
                        except Exception as e:
                            self.logger.error(f"Error downloading image for {query}: {e}")
                        
                        # Add random delay between downloads
                        time.sleep(random.uniform(0.5, 1.5))
                    
                    # Track profile stats
                    profile_stats[query] = len(profile_images)
                
                except Exception as e:
                    self.logger.error(f"Error processing query {query}: {e}")
                    continue
        
        except Exception as e:
            self.logger.error(f"Unexpected error in Twitter scraping: {e}")
        
        finally:
            # Close browser
            if driver:
                driver.quit()
        
        # Log statistics
        self.logger.info("Twitter scraping completed.")
        for query, count in profile_stats.items():
            self.logger.info(f"Search '{query}': {count} images")
        self.logger.info(f"Total images downloaded: {len(all_images)}")
        
        return all_images

async def scrape_twitter_profiles(
    profile_count=5,
    max_profiles_to_scrape=5,
    max_images_per_profile=10,
    output_dir="data/downloaded_images/twitter"
) -> Dict:
    """
    Run the Twitter profile scraper asynchronously.
    
    Args:
        profile_count (int): Target number of profiles to find
        max_profiles_to_scrape (int): Maximum number of profiles to scrape
        max_images_per_profile (int): Maximum images per profile
        output_dir (str): Directory to save downloaded images
    
    Returns:
        Dict: Results containing:
            - profiles_found (int): Number of profiles found
            - images_downloaded (int): Number of images downloaded
            - faces_detected (int): Number of faces detected
            - runtime_seconds (float): Total runtime in seconds
    """
    start_time = time.time()
    
    # Initialize scraper
    scraper = SeleniumTwitterScraper(output_dir=output_dir)
    
    try:
        # Run the scraper
        downloaded_images = scraper.run(
            max_profiles=max_profiles_to_scrape,
            max_images_per_profile=max_images_per_profile
        )
        
        # Calculate runtime
        runtime = time.time() - start_time
        
        # Return results in expected format
        return {
            'profiles_found': max_profiles_to_scrape,  # Number of search queries used
            'images_downloaded': len(downloaded_images),
            'faces_detected': 0,  # Face detection happens in processing stage
            'runtime_seconds': runtime
        }
        
    except Exception as e:
        scraper.logger.error(f"Error in Twitter scraping: {e}")
        return {
            'profiles_found': 0,
            'images_downloaded': 0,
            'faces_detected': 0,
            'runtime_seconds': time.time() - start_time
        }