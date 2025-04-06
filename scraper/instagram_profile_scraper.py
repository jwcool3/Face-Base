import asyncio
import aiohttp
import re
import random
import time
import os
import json
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from utils.logger import get_logger
from scraper.utils import ensure_directory

class InstagramProfileScraper:
    """Scrapes Instagram profiles to collect public images."""
    
    def __init__(self, profiles_file="data/instagram_profiles.json", output_dir="data/downloaded_images/instagram"):
        self.logger = get_logger(__name__)
        self.profiles_file = profiles_file
        self.output_dir = output_dir
        self.profiles = []
        
        # Ensure output directory exists
        ensure_directory(self.output_dir)
        
        # User agent rotation for avoiding blocks
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.1 Safari/605.1.15',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36',
            'Mozilla/5.0 (iPhone; CPU iPhone OS 16_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.1 Mobile/15E148 Safari/604.1'
        ]
        
        # Pattern to extract image URLs from Instagram
        self.image_pattern = re.compile(r'https://\w+\.cdninstagram\.com/\w+/[^"\']+\.jpg')
        
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
    
    def _get_random_headers(self):
        """Get random headers to avoid detection."""
        user_agent = random.choice(self.user_agents)
        return {
            'User-Agent': user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://www.google.com/',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0'
        }
    
    async def fetch_profile(self, session, username):
        """Fetch an Instagram profile page with more reliable approach."""
        # Try multiple approaches to get profile content
        
        # Approach 1: Direct Instagram URL
        profile_url = f"https://www.instagram.com/{username}/"
        
        try:
            headers = self._get_random_headers()
            async with session.get(profile_url, headers=headers, timeout=30) as response:
                if response.status == 200:
                    html_content = await response.text()
                    # Quick check if content seems valid
                    if '"profile_pic_url"' in html_content or 'profilePage' in html_content:
                        self.logger.debug(f"Successfully fetched profile @{username} directly")
                        return html_content
        except Exception as e:
            self.logger.debug(f"Error with direct fetch for @{username}: {e}")
        
        # Approach 2: Try through a search engine
        search_url = f"https://www.google.com/search?q=instagram+{username}+profile&tbm=isch"
        
        try:
            headers = self._get_random_headers()
            async with session.get(search_url, headers=headers, timeout=30) as response:
                if response.status == 200:
                    self.logger.debug(f"Using search engine for @{username}")
                    return await response.text()
        except Exception as e:
            self.logger.debug(f"Error with search approach for @{username}: {e}")
        
        # Approach 3: Try public third-party Instagram viewers
        viewer_url = f"https://imginn.com/{username}/"
        
        try:
            headers = self._get_random_headers()
            async with session.get(viewer_url, headers=headers, timeout=30) as response:
                if response.status == 200:
                    self.logger.debug(f"Using third-party viewer for @{username}")
                    return await response.text()
        except Exception as e:
            self.logger.debug(f"Error with viewer approach for @{username}: {e}")
        
        self.logger.warning(f"All approaches failed for @{username}")
        return None
    
    def extract_image_urls(self, html_content, username):
        """Extract image URLs with more robust methods."""
        if not html_content:
            return []
            
        image_urls = []
        
        # Approach 1: Look for Instagram CDN URLs
        cdn_patterns = [
            # Standard Instagram CDN patterns
            r'https://\w+\.cdninstagram\.com/\w+/[^"\']+\.jpg',
            r'https://\w+\.cdninstagram\.com/\w+/[^"\']+\.png',
            r'https://instagram\.\w+\.fbcdn\.net/\w+/[^"\']+\.jpg',
            r'https://scontent[^"\']+\.jpg',
            
            # Google Images might have these versions
            r'https://\w+\.ggpht\.com/[^"\']+',
            r'https://encrypted-tbn0\.gstatic\.com/images\?[^"\']+',
        ]
        
        for pattern in cdn_patterns:
            matches = re.findall(pattern, html_content)
            image_urls.extend(matches)
        
        # Approach 2: Try to extract from JSON data in the page
        try:
            # Look for JSON data that might contain image URLs
            json_match = re.search(r'window\._sharedData\s*=\s*({.*?});</script>', html_content)
            if json_match:
                json_data = json.loads(json_match.group(1))
                
                # Extract from user media
                if 'entry_data' in json_data and 'ProfilePage' in json_data['entry_data']:
                    user_media = json_data['entry_data']['ProfilePage'][0]['graphql']['user']['edge_owner_to_timeline_media']['edges']
                    for edge in user_media:
                        if 'node' in edge and 'display_url' in edge['node']:
                            image_urls.append(edge['node']['display_url'])
        except Exception as e:
            self.logger.debug(f"Error extracting from JSON data: {e}")
        
        # Approach 3: If this is from a search engine, look for standard img tags
        if 'google.com' in html_content or 'bing.com' in html_content:
            try:
                soup = BeautifulSoup(html_content, 'lxml')
                
                # Find all image tags
                for img in soup.find_all('img'):
                    src = img.get('src')
                    if src and (username in img.get('alt', '') or username in img.get('title', '')):
                        image_urls.append(src)
                        
                # Also look for data-src attributes which often contain the full image
                for img in soup.find_all('img', attrs={'data-src': True}):
                    data_src = img.get('data-src')
                    if data_src:
                        image_urls.append(data_src)
            except Exception as e:
                self.logger.debug(f"Error parsing search engine HTML: {e}")
        
        # Approach 4: If using a third-party viewer
        if 'imginn.com' in html_content or 'instanavigation' in html_content:
            try:
                soup = BeautifulSoup(html_content, 'lxml')
                
                # Find all image containers
                for img in soup.select('div.img-box img, div.photo img'):
                    src = img.get('src')
                    if src:
                        image_urls.append(src)
            except Exception as e:
                self.logger.debug(f"Error parsing third-party viewer: {e}")
        
        # Clean URLs - remove escaped characters and duplicates
        clean_urls = []
        for url in image_urls:
            # Remove any escaped characters
            url = url.replace('\\u0026', '&')
            url = url.replace('\\/', '/')
            
            # Remove query parameters for deduplication
            base_url = url.split('?')[0]
            
            if base_url not in clean_urls:
                clean_urls.append(base_url)
        
        self.logger.info(f"Found {len(clean_urls)} unique images for @{username}")
        return clean_urls
    
    async def download_image(self, session, url, username, image_index):
        """Download a single image with more robust error handling."""
        try:
            # Add referer header to avoid anti-scraping measures
            headers = self._get_random_headers()
            headers['Referer'] = f"https://www.instagram.com/{username}/"
            
            async with session.get(url, headers=headers, timeout=30) as response:
                if response.status == 200:
                    # Check content type
                    content_type = response.headers.get('Content-Type', '')
                    if not content_type.startswith(('image/', 'application/octet-stream')):
                        self.logger.warning(f"Skipping non-image content: {content_type} for URL {url}")
                        return None
                    
                    # Create user directory
                    user_dir = os.path.join(self.output_dir, username)
                    os.makedirs(user_dir, exist_ok=True)
                    
                    # Generate filename
                    filename = f"{username}_{image_index}.jpg"
                    filepath = os.path.join(user_dir, filename)
                    
                    # Save image
                    with open(filepath, 'wb') as f:
                        f.write(await response.read())
                    
                    self.logger.debug(f"Downloaded {url} to {filepath}")
                    return filepath
                else:
                    self.logger.warning(f"Failed to download image {url}: HTTP {response.status}")
                    return None
        except Exception as e:
            self.logger.error(f"Error downloading image {url}: {e}")
            return None
    
    async def find_public_photos_for_profile(self, session, username):
        """Find public photos of a profile using search engines."""
        search_url = f"https://www.google.com/search?q=instagram+{username}+photo&tbm=isch"
        
        try:
            self.logger.info(f"Searching for public photos of @{username}")
            headers = self._get_random_headers()
            async with session.get(search_url, headers=headers, timeout=30) as response:
                if response.status == 200:
                    html_content = await response.text()
                    
                    # Extract image URLs
                    image_urls = []
                    
                    # Regex for image URLs in Google Images results
                    patterns = [
                        r'https://\w+\.ggpht\.com/[^"\']+',
                        r'https://encrypted-tbn0\.gstatic\.com/images\?[^"\']+',
                        r'"ou":"(https://[^"]+)"',  # Original URL in JSON data
                    ]
                    
                    for pattern in patterns:
                        if pattern.startswith('"ou":'):
                            # This extracts from JSON data
                            matches = re.findall(pattern, html_content)
                            image_urls.extend(matches)
                        else:
                            # Standard regex
                            matches = re.findall(pattern, html_content)
                            image_urls.extend(matches)
                    
                    # Parse HTML to extract more image URLs
                    try:
                        soup = BeautifulSoup(html_content, 'lxml')
                        
                        # Find all image tags
                        for img in soup.find_all('img'):
                            src = img.get('src')
                            if src and src.startswith('http'):
                                image_urls.append(src)
                                
                        # Also look for original URLs in JSON data
                        for script in soup.find_all('script'):
                            script_text = script.string
                            if script_text and '"ou":"' in script_text:
                                matches = re.findall(r'"ou":"(https://[^"]+)"', script_text)
                                image_urls.extend(matches)
                    except Exception as e:
                        self.logger.debug(f"Error parsing search HTML: {e}")
                    
                    # Clean URLs
                    clean_urls = []
                    for url in image_urls:
                        # Remove any escaped characters
                        url = url.replace('\\u0026', '&')
                        url = url.replace('\\/', '/')
                        
                        # Remove duplicates
                        if url not in clean_urls:
                            clean_urls.append(url)
                    
                    self.logger.info(f"Found {len(clean_urls)} potential public photos for @{username}")
                    return clean_urls
                    
        except Exception as e:
            self.logger.error(f"Error searching for photos of @{username}: {e}")
        
        return []
    
    async def scrape_profile(self, session, username, max_images=10):
        """Scrape images from an Instagram profile with fallback methods."""
        self.logger.info(f"Scraping profile: @{username}")
        
        # Method 1: Try to fetch the profile directly
        html_content = await self.fetch_profile(session, username)
        image_urls = []
        
        if html_content:
            image_urls = self.extract_image_urls(html_content, username)
        
        # Method 2: If no images found, try the search engine approach
        if not image_urls:
            self.logger.info(f"No images found directly. Trying search engine for @{username}")
            image_urls = await self.find_public_photos_for_profile(session, username)
        
        # Limit the number of images
        if len(image_urls) > max_images:
            image_urls = image_urls[:max_images]
        
        # Download images
        downloaded_images = []
        for i, url in enumerate(image_urls):
            filepath = await self.download_image(session, url, username, i)
            if filepath:
                downloaded_images.append(filepath)
            
            # Add delay between image downloads
            await asyncio.sleep(random.uniform(1, 3))
        
        self.logger.info(f"Downloaded {len(downloaded_images)} images for @{username}")
        return downloaded_images
    
    async def run(self, max_profiles=50, max_images_per_profile=10, max_concurrent=5):
        """Scrape images from Instagram profiles."""
        if not self.profiles:
            self.logger.error("No profiles to scrape. Run the profile finder first.")
            return []
        
        self.logger.info(f"Starting Instagram profile scraper. "
                        f"Will scrape up to {max_profiles} profiles, "
                        f"{max_images_per_profile} images per profile")
        
        # Limit the number of profiles
        profiles_to_scrape = self.profiles[:max_profiles]
        
        all_images = []
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def scrape_with_semaphore(username):
            async with semaphore:
                return await self.scrape_profile(session, username, max_images_per_profile)
        
        async with aiohttp.ClientSession() as session:
            # Prepare tasks
            tasks = [scrape_with_semaphore(username) for username in profiles_to_scrape]
            
            # Use gather with return_exceptions to handle errors gracefully
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            for username, result in zip(profiles_to_scrape, results):
                if isinstance(result, Exception):
                    self.logger.error(f"Error scraping @{username}: {result}")
                else:
                    all_images.extend(result)
        
        self.logger.info(f"Instagram profile scraper completed. Downloaded {len(all_images)} total images.")
        return all_images

# Function to run from command line
async def scrape_instagram_profiles(max_profiles=50, max_images_per_profile=10, 
                                  profiles_file="data/instagram_profiles.json",
                                  output_dir="data/downloaded_images/instagram"):
    scraper = InstagramProfileScraper(profiles_file=profiles_file, output_dir=output_dir)
    images = await scraper.run(
        max_profiles=max_profiles,
        max_images_per_profile=max_images_per_profile
    )
    return images

# Command line entry point
def main():
    import argparse
    parser = argparse.ArgumentParser(description='Scrape public Instagram profiles')
    parser.add_argument('--profiles', type=int, default=50, help='Maximum number of profiles to scrape')
    parser.add_argument('--images', type=int, default=10, help='Maximum images per profile')
    parser.add_argument('--input', type=str, default="data/instagram_profiles.json", help='Profiles input file')
    parser.add_argument('--output', type=str, default="data/downloaded_images/instagram", help='Output directory')
    
    args = parser.parse_args()
    
    asyncio.run(scrape_instagram_profiles(
        max_profiles=args.profiles,
        max_images_per_profile=args.images,
        profiles_file=args.input,
        output_dir=args.output
    ))

if __name__ == "__main__":
    main()