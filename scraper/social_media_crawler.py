import asyncio
import aiohttp
import time
import random
import os
from urllib.parse import urlparse
from bs4 import BeautifulSoup
import json
from utils.logger import get_logger
from utils.config import Config
from scraper.utils import get_absolute_url
from scraper.person_detector import RealPersonDetector

class SocialMediaCrawler:
    """Web crawler specialized for public social media and community sites."""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        self.config = Config()
        
        # Load crawler settings from config
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Referer': 'https://www.google.com/'
        }
        
        self.delay = self.config.getfloat('Crawler', 'RequestDelay', fallback=1.5)  # Longer delay for social media
        self.max_retries = self.config.getint('Crawler', 'MaxRetries', fallback=3)
        self.timeout = self.config.getint('Crawler', 'Timeout', fallback=30)
        
        # Social media specific settings
        self.scroll_simulation = True  # Simulate scrolling behavior
        self.person_detector = RealPersonDetector()
        
        # Initialize counters
        self.pages_visited = 0
        self.images_found = 0
        self.real_person_images = 0
    
    async def fetch_with_scroll(self, session, url, scroll_count=3):
        """
        Fetch a URL with simulated scrolling for infinite-scroll social sites.
        
        Args:
            session (aiohttp.ClientSession): The HTTP session.
            url (str): URL to fetch.
            scroll_count (int): Number of simulated scrolls.
            
        Returns:
            str: Combined HTML content or None if failed.
        """
        try:
            # Initial page load
            async with session.get(url, headers=self.headers, timeout=self.timeout) as response:
                if response.status != 200:
                    self.logger.warning(f"Failed to fetch {url}: HTTP {response.status}")
                    return None
                
                html_content = await response.text()
                base_html = html_content
                
                # For sites with infinite scroll, we may need additional requests
                if self.scroll_simulation and scroll_count > 0:
                    # Find any pagination or "load more" indicators
                    soup = BeautifulSoup(html_content, 'lxml')
                    load_more_links = soup.select('a[href*="page="], a[href*="cursor="], .load-more, button[data-testid="more"]')
                    
                    for i in range(min(len(load_more_links), scroll_count)):
                        # Add delay between "scrolls"
                        await asyncio.sleep(self.delay + random.random())
                        
                        # Get the next page URL or construct it
                        if load_more_links and i < len(load_more_links):
                            next_url = load_more_links[i].get('href')
                            if next_url and not next_url.startswith('http'):
                                next_url = get_absolute_url(url, next_url)
                                
                            if next_url:
                                try:
                                    async with session.get(next_url, headers=self.headers, timeout=self.timeout) as next_resp:
                                        if next_resp.status == 200:
                                            next_html = await next_resp.text()
                                            base_html += next_html
                                except Exception as e:
                                    self.logger.error(f"Error during scroll simulation: {e}")
                
                return base_html
                
        except asyncio.TimeoutError:
            self.logger.warning(f"Timeout fetching {url}")
            return None
        except Exception as e:
            self.logger.error(f"Error fetching {url}: {e}")
            return None
    
    async def extract_social_image_urls(self, html_content, base_url):
        """
        Extract image URLs from social media HTML with specialized handling.
        
        Args:
            html_content (str): HTML content of the page.
            base_url (str): Base URL for resolving relative links.
            
        Returns:
            list: List of image URLs.
        """
        if not html_content:
            return []
            
        image_urls = []
        soup = BeautifulSoup(html_content, 'lxml')
        
        # Standard image tags
        for img in soup.find_all('img'):
            src = img.get('src') or img.get('data-src') or img.get('data-delayed-src')
            if src:
                # Skip tiny images and icons
                if 'icon' in src.lower() or 'logo' in src.lower():
                    continue
                    
                # Get width/height if available
                width = img.get('width', '')
                height = img.get('height', '')
                
                try:
                    # Skip very small images
                    if width and height and (int(width) < 100 or int(height) < 100):
                        continue
                except (ValueError, TypeError):
                    pass
                
                # Add the image URL
                full_url = get_absolute_url(base_url, src)
                image_urls.append(full_url)
        
        # Special handling for social media sites
        
        # Instagram-style
        for div in soup.select('div[role="button"] img'):
            src = div.get('src')
            if src:
                image_urls.append(get_absolute_url(base_url, src))
        
        # Facebook-style
        for img in soup.select('a[aria-label*="photo"] img'):
            src = img.get('src')
            if src:
                image_urls.append(get_absolute_url(base_url, src))
        
        # Twitter-style
        for img in soup.select('div[data-testid="tweetPhoto"] img'):
            src = img.get('src')
            if src:
                image_urls.append(get_absolute_url(base_url, src))
        
        # Pinterest-style
        for img in soup.select('div[data-test-id="pinWrapper"] img'):
            src = img.get('src')
            if src:
                image_urls.append(get_absolute_url(base_url, src))
        
        # Remove duplicates while preserving order
        seen = set()
        unique_urls = []
        for url in image_urls:
            if url not in seen:
                seen.add(url)
                unique_urls.append(url)
        
        return unique_urls
    
    async def crawl_social_media(self, start_url, max_pages=20, max_images=100):
        """
        Crawl social media starting from a specific URL.
        
        Args:
            start_url (str): Starting URL.
            max_pages (int): Maximum number of pages to crawl.
            max_images (int): Maximum number of images to find.
            
        Returns:
            list: List of image URLs likely containing real people.
        """
        self.logger.info(f"Starting social media crawl from {start_url}")
        
        # Extract domain from start_url
        domain = urlparse(start_url).netloc
        
        visited_urls = set()
        to_visit_urls = {start_url}
        all_images = []
        
        start_time = time.time()
        
        # Add priority to pages that likely contain images
        high_priority_patterns = [
            r'photo', r'image', r'gallery', r'portrait', r'selfie', 
            r'popular', r'top', r'hot', r'best', r'featured'
        ]
        
        # Use this function to score URLs
        def score_url(url):
            score = 0
            for pattern in high_priority_patterns:
                if pattern in url.lower():
                    score += 1
            return score
        
        async with aiohttp.ClientSession() as session:
            while to_visit_urls and len(visited_urls) < max_pages and len(all_images) < max_images:
                # Instead of just popping, prioritize URLs
                if to_visit_urls:
                    # Sort by score and get highest scoring URL
                    url = sorted(to_visit_urls, key=score_url, reverse=True)[0]
                    to_visit_urls.remove(url)
                
                # Skip if already visited
                if url in visited_urls:
                    continue
                
                self.logger.debug(f"Crawling: {url}")
                
                # Mark as visited
                visited_urls.add(url)
                
                # Fetch the page with scroll simulation
                html_content = await self.fetch_with_scroll(session, url)
                if not html_content:
                    continue
                
                # Extract image URLs
                page_image_urls = await self.extract_social_image_urls(html_content, url)
                self.logger.info(f"Found {len(page_image_urls)} images on {url}")
                
                # Skip URL filtering and directly download all image URLs
                remaining = max_images - len(all_images)
                if remaining <= 0:
                    break
                
                # Take only unique images we haven't seen before
                new_images = [img for img in page_image_urls if img not in all_images]
                all_images.extend(new_images[:remaining])
                
                # Extract links to visit next
                soup = BeautifulSoup(html_content, 'lxml')
                for a_tag in soup.find_all('a'):
                    href = a_tag.get('href')
                    if href:
                        link = get_absolute_url(url, href)
                        # Only follow links within the same domain
                        if domain in link and link not in visited_urls and link not in to_visit_urls:
                            to_visit_urls.add(link)
                
                # Update counters
                self.pages_visited += 1
                
                # Respect robots.txt with a delay
                await asyncio.sleep(self.delay + random.random())
        
        # Report crawl statistics
        elapsed = time.time() - start_time
        self.logger.info(f"Crawl completed in {elapsed:.2f}s. Visited {len(visited_urls)} pages")
        self.logger.info(f"Found {len(all_images)} images")
        
        return all_images