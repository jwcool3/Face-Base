import os
import time
import json
import random
import urllib.request
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from utils.logger import get_logger

class SeleniumInstagramScraper:
    """Uses Selenium to scrape Instagram profiles more effectively."""
    
    def __init__(self, profiles_file="data/instagram_profiles.json", output_dir="data/downloaded_images/instagram"):
        self.logger = get_logger(__name__)
        self.profiles_file = profiles_file
        self.output_dir = output_dir
        self.profiles = []
        
        # Ensure output directory exists
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Load profiles
        self._load_profiles()
        
    def _load_profiles(self):
        """Load Instagram profiles from file."""
        if os.path.exists(self.profiles_file):
            try:
                with open(self.profiles_file, 'r') as f:
                    data = json.load(f)
                    if 'profiles' in data:
                        self.profiles = data['profiles']
                        self.logger.info(f"Loaded {len(self.profiles)} profiles from {self.profiles_file}")
            except Exception as e:
                self.logger.error(f"Error loading profiles: {e}")
    
    def _setup_driver(self):
        """Set up the Selenium WebDriver."""
        try:
            chrome_options = Options()
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=1920,1080")
            
            # Add random user agent
            user_agents = [
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36',
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.1 Safari/605.1.15',
                'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36'
            ]
            chrome_options.add_argument(f"--user-agent={random.choice(user_agents)}")
            
            # Initialize the driver
            driver = webdriver.Chrome(options=chrome_options)
            
            # Set timeouts
            driver.set_page_load_timeout(30)
            
            return driver
        except Exception as e:
            self.logger.error(f"Error setting up WebDriver: {e}")
            return None
            
    def _download_image(self, img_url, username, img_index):
        """Download image from URL."""
        try:
            # Create user directory
            user_dir = os.path.join(self.output_dir, username)
            os.makedirs(user_dir, exist_ok=True)
            
            # Generate filename
            filename = f"{username}_{img_index}.jpg"
            filepath = os.path.join(user_dir, filename)
            
            # Download the image with proper headers
            opener = urllib.request.build_opener()
            opener.addheaders = [
                ('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36'),
                ('Referer', 'https://www.google.com/')
            ]
            urllib.request.install_opener(opener)
            
            # Download image
            urllib.request.urlretrieve(img_url, filepath)
            self.logger.debug(f"Downloaded image to {filepath}")
            
            # Verify the file exists and has content
            if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
                return filepath
            else:
                self.logger.warning(f"Downloaded file is empty or missing: {filepath}")
                if os.path.exists(filepath):
                    os.remove(filepath)
                return None
                
        except Exception as e:
            self.logger.error(f"Error downloading image {img_url}: {e}")
            return None
    
    def scrape_via_search(self, username, max_images=10):
        """Scrape Instagram profile via search engines."""
        self.logger.info(f"Scraping profile via search: @{username}")
        
        downloaded_images = []
        driver = self._setup_driver()
        
        if not driver:
            return downloaded_images
            
        try:
            # Search for Instagram profile on Google Images
            search_url = f"https://www.google.com/search?q=instagram+{username}+photo&tbm=isch"
            driver.get(search_url)
            
            # Wait for images to load
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "img"))
            )
            
            # Scroll down to load more images
            for _ in range(3):
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)
            
            # Extract image URLs
            img_elements = driver.find_elements(By.TAG_NAME, "img")
            img_urls = []
            
            for img in img_elements:
                src = img.get_attribute("src")
                if src and src.startswith("http"):
                    img_urls.append(src)
            
            self.logger.info(f"Found {len(img_urls)} image URLs for @{username}")
            
            # Limit the number of images
            if len(img_urls) > max_images:
                img_urls = img_urls[:max_images]
            
            # Download images
            for i, url in enumerate(img_urls):
                filepath = self._download_image(url, username, i)
                if filepath:
                    downloaded_images.append(filepath)
                
                # Add delay between downloads
                time.sleep(random.uniform(0.5, 1.5))
            
        except Exception as e:
            self.logger.error(f"Error scraping via search for @{username}: {e}")
        finally:
            # Close the driver
            driver.quit()
        
        self.logger.info(f"Downloaded {len(downloaded_images)} images for @{username}")
        return downloaded_images
    
    def scrape_public_profile(self, username, max_images=10):
        """Try to directly scrape a public Instagram profile."""
        self.logger.info(f"Attempting direct scrape for profile: @{username}")
        
        downloaded_images = []
        driver = self._setup_driver()
        
        if not driver:
            return downloaded_images
            
        try:
            # Try to access the profile directly
            profile_url = f"https://www.instagram.com/{username}/"
            driver.get(profile_url)
            
            # Wait for page to load
            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.TAG_NAME, "img"))
                )
            except TimeoutException:
                self.logger.warning(f"Timeout waiting for page to load: {profile_url}")
                return []
            
            # Check if we're redirected to login page
            if "instagram.com/accounts/login" in driver.current_url:
                self.logger.warning(f"Redirected to login page for @{username}")
                return []
            
            # Extract image URLs
            img_elements = driver.find_elements(By.TAG_NAME, "img")
            img_urls = []
            
            for img in img_elements:
                src = img.get_attribute("src")
                if src and "instagram.com" in src and src.endswith((".jpg", ".jpeg", ".png")):
                    img_urls.append(src)
            
            self.logger.info(f"Found {len(img_urls)} direct image URLs for @{username}")
            
            # Limit the number of images
            if len(img_urls) > max_images:
                img_urls = img_urls[:max_images]
            
            # Download images
            for i, url in enumerate(img_urls):
                filepath = self._download_image(url, username, i)
                if filepath:
                    downloaded_images.append(filepath)
                
                # Add delay between downloads
                time.sleep(random.uniform(0.5, 1.5))
            
        except Exception as e:
            self.logger.error(f"Error directly scraping @{username}: {e}")
        finally:
            # Close the driver
            driver.quit()
        
        return downloaded_images
    
    def scrape_profile(self, username, max_images=10):
        """Scrape an Instagram profile using multiple methods."""
        self.logger.info(f"Scraping profile: @{username}")
        
        # First try direct method
        downloaded_images = self.scrape_public_profile(username, max_images)
        
        # If direct method failed, try search engine
        if not downloaded_images:
            self.logger.info(f"Direct scraping failed for @{username}, trying search method")
            downloaded_images = self.scrape_via_search(username, max_images)
        
        self.logger.info(f"Downloaded total of {len(downloaded_images)} images for @{username}")
        return downloaded_images
    
    def run(self, max_profiles=5, max_images_per_profile=10):
        """Run the Instagram scraper on multiple profiles."""
        if not self.profiles:
            self.logger.error("No profiles to scrape. Run the profile finder first.")
            return []
        
        self.logger.info(f"Starting Selenium Instagram scraper on {max_profiles} profiles")
        
        # Limit the number of profiles
        profiles_to_scrape = self.profiles[:max_profiles]
        
        all_images = []
        profile_stats = {}
        
        for username in profiles_to_scrape:
            profile_images = self.scrape_profile(username, max_images_per_profile)
            all_images.extend(profile_images)
            profile_stats[username] = len(profile_images)
            
            # Add delay between profiles
            time.sleep(random.uniform(2, 5))
        
        # Log summary
        self.logger.info("Instagram scraping completed. Summary:")
        for username, count in profile_stats.items():
            self.logger.info(f"- @{username}: {count} images")
        
        self.logger.info(f"Total images downloaded: {len(all_images)}")
        return all_images

def scrape_instagram_profiles(max_profiles=5, max_images_per_profile=10, 
                            profiles_file="data/instagram_profiles.json",
                            output_dir="data/downloaded_images/instagram"):
    """Run the Selenium Instagram scraper."""
    scraper = SeleniumInstagramScraper(profiles_file=profiles_file, output_dir=output_dir)
    return scraper.run(max_profiles=max_profiles, max_images_per_profile=max_images_per_profile)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Scrape Instagram profiles using Selenium')
    parser.add_argument('--profiles', type=int, default=5, help='Number of profiles to scrape')
    parser.add_argument('--images', type=int, default=10, help='Max images per profile')
    parser.add_argument('--input', type=str, default="data/instagram_profiles.json", help='Profiles input file')
    parser.add_argument('--output', type=str, default="data/downloaded_images/instagram", help='Output directory')
    
    args = parser.parse_args()
    
    scrape_instagram_profiles(
        max_profiles=args.profiles,
        max_images_per_profile=args.images,
        profiles_file=args.input,
        output_dir=args.output
    )