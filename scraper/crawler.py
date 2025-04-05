import asyncio
import aiohttp
from urllib.parse import urlparse
from bs4 import BeautifulSoup
import time
import random
from .utils import get_absolute_url, save_crawler_state, load_crawler_state
from utils.logger import get_logger
from utils.config import Config

class WebCrawler:
    """
    Asynchronous web crawler for fetching images from websites.
    """
    
    def __init__(self):
        """Initialize the web crawler with configuration settings."""
        self.logger = get_logger(__name__)
        self.config = Config()
        
        # Load crawler settings from config
        self.headers = {
            'User-Agent': self.config.get('Crawler', 'UserAgent', 
                fallback='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
        }
        
        self.delay = self.config.getfloat('Crawler', 'RequestDelay', fallback=0.5)
        self.max_retries = self.config.getint('Crawler', 'MaxRetries', fallback=3)
        self.timeout = self.config.getint('Crawler', 'Timeout', fallback=30)
        
        # Initialize counters
        self.pages_visited = 0
        self.images_found = 0
    
    async def fetch(self, session, url, retries=0):
        """
        Fetch a URL with retry capability.
        
        Args:
            session (aiohttp.ClientSession): The HTTP session.
            url (str): URL to fetch.
            retries (int): Current retry count.
            
        Returns:
            str: HTML content or None if failed.
        """
        try:
            async with session.get(url, headers=self.headers, timeout=self.timeout) as response:
                if response.status == 200:
                    return await response.text()
                elif response.status == 429 and retries < self.max_retries:  # Too Many Requests
                    retry_after = int(response.headers.get('Retry-After', self.delay * 2))
                    self.logger.warning(f"Rate limited on {url}, waiting {retry_after}s before retry")
                    await asyncio.sleep(retry_after)
                    return await self.fetch(session, url, retries + 1)
                else:
                    self.logger.warning(f"Failed to fetch {url}: HTTP {response.status}")
                    return None
        except asyncio.TimeoutError:
            self.logger.warning(f"Timeout fetching {url}")
            if retries < self.max_retries:
                await asyncio.sleep(self.delay * (retries + 1))
                return await self.fetch(session, url, retries + 1)
            return None
        except Exception as e:
            self.logger.error(f"Error fetching {url}: {e}")
            return None
    
    async def crawl_page(self, session, url, domain, visited):
        """
        Crawl a single page to extract links and images.
        
        Args:
            session (aiohttp.ClientSession): The HTTP session.
            url (str): URL to crawl.
            domain (str): Domain to stay within.
            visited (set): Set of already visited URLs.
            
        Returns:
            tuple: (page_urls, image_urls) sets of new pages and images.
        """
        page_urls = set()
        image_urls = set()
        
        html = await self.fetch(session, url)
        if not html:
            return page_urls, image_urls
        
        try:
            soup = BeautifulSoup(html, 'lxml')
            
            # Extract image URLs
            for img_tag in soup.find_all('img'):
                src = img_tag.get('src')
                if src:
                    img_url = get_absolute_url(url, src)
                    image_urls.add(img_url)
                    self.images_found += 1
            
            # Extract page links
            for a_tag in soup.find_all('a'):
                href = a_tag.get('href')
                if href:
                    link = get_absolute_url(url, href)
                    # Only follow links within the same domain
                    if domain in link and link not in visited:
                        page_urls.add(link)
            
            self.pages_visited += 1
            if self.pages_visited % 50 == 0:
                self.logger.info(f"Crawled {self.pages_visited} pages, found {self.images_found} images")
                
        except Exception as e:
            self.logger.error(f"Error processing page {url}: {e}")
        
        # Add a delay to avoid overloading the server
        delay = self.delay * (0.5 + random.random())
        await asyncio.sleep(delay)
        
        return page_urls, image_urls
    
    async def crawl_domain(self, start_url, max_pages=None, state_file='crawler_state.json'):
        """
        Crawl a domain starting from a specific URL.
        
        Args:
            start_url (str): Starting URL.
            max_pages (int, optional): Maximum number of pages to crawl.
            state_file (str): File to save/load crawler state.
            
        Returns:
            set: Set of image URLs found.
        """
        self.logger.info(f"Starting crawl from {start_url}")
        
        # Extract domain from start_url
        domain = urlparse(start_url).netloc
        
        # Load state if it exists
        state = load_crawler_state(state_file)
        if state:
            visited_urls = set(state['visited_urls'])
            to_visit_urls = set(state['to_visit_urls'])
            all_image_urls = set(state['all_image_urls'])
            self.pages_visited = len(visited_urls)
            self.images_found = len(all_image_urls)
            self.logger.info(f"Resuming from saved state with {self.pages_visited} pages visited and {self.images_found} images found")
        else:
            visited_urls = set()
            to_visit_urls = {start_url}
            all_image_urls = set()
        
        start_time = time.time()
        
        async with aiohttp.ClientSession() as session:
            while to_visit_urls and (max_pages is None or self.pages_visited < max_pages):
                # Get the next URL to visit
                url = to_visit_urls.pop()
                
                # Skip if already visited
                if url in visited_urls:
                    continue
                
                self.logger.debug(f"Crawling: {url}")
                
                # Mark as visited
                visited_urls.add(url)
                
                # Crawl the page
                new_page_urls, new_image_urls = await self.crawl_page(session, url, domain, visited_urls)
                
                # Update URLs to visit and image URLs
                to_visit_urls.update(new_page_urls - visited_urls)
                all_image_urls.update(new_image_urls)
                
                # Save state periodically
                if self.pages_visited % 100 == 0 or not to_visit_urls:
                    save_crawler_state({
                        'visited_urls': list(visited_urls),
                        'to_visit_urls': list(to_visit_urls),
                        'all_image_urls': list(all_image_urls)
                    }, state_file)
        
        elapsed = time.time() - start_time
        self.logger.info(f"Crawl completed in {elapsed:.2f}s")
        self.logger.info(f"Visited {self.pages_visited} pages, found {len(all_image_urls)} unique images")
        
        # Save final state
        save_crawler_state({
            'visited_urls': list(visited_urls),
            'to_visit_urls': list(to_visit_urls),
            'all_image_urls': list(all_image_urls)
        }, state_file)
        
        return all_image_urls

def run_crawler(start_url, max_pages=None, state_file='crawler_state.json'):
    """
    Run the crawler from command line or another module.
    
    Args:
        start_url (str): Starting URL.
        max_pages (int, optional): Maximum number of pages to crawl.
        state_file (str): File to save/load crawler state.
        
    Returns:
        list: List of image URLs found.
    """
    crawler = WebCrawler()
    image_urls = asyncio.run(crawler.crawl_domain(start_url, max_pages, state_file))
    return list(image_urls)
