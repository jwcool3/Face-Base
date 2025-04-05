import os
import asyncio
import aiohttp
import time
import json
from .utils import sanitize_filename, ensure_directory
from utils.logger import get_logger
from utils.config import Config

class ImageDownloader:
    """
    Asynchronous image downloader to download images from URLs.
    """
    
    def __init__(self):
        """Initialize the image downloader with configuration settings."""
        self.logger = get_logger(__name__)
        self.config = Config()
        
        # Load downloader settings from config
        self.headers = {
            'User-Agent': self.config.get('Downloader', 'UserAgent', 
                fallback='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
        }
        
        self.concurrent_downloads = self.config.getint('Downloader', 'ConcurrentDownloads', fallback=20)
        self.retry_count = self.config.getint('Downloader', 'RetryCount', fallback=3)
        self.timeout = self.config.getint('Downloader', 'Timeout', fallback=30)
        
        # Get the download directory from config
        self.base_download_dir = self.config.get('Paths', 'DownloadFolder', fallback='data/downloaded_images')
        ensure_directory(self.base_download_dir)
    
    async def download_image(self, session, url, save_dir, downloaded_count, total_images, metadata, retry_count=0):
        """
        Download a single image.
        
        Args:
            session (aiohttp.ClientSession): The HTTP session.
            url (str): URL of the image to download.
            save_dir (str): Directory to save the image.
            downloaded_count (dict): Reference to counter for downloaded images.
            total_images (int): Total number of images to download.
            metadata (dict): Dictionary to store metadata about downloaded images.
            retry_count (int): Current retry count.
            
        Returns:
            str: The URL of the downloaded image, or None if failed.
        """
        try:
            async with session.get(url, headers=self.headers, timeout=self.timeout) as response:
                if response.status == 200:
                    # Create a filename based on the URL hash
                    filename = sanitize_filename(url)
                    file_path = os.path.join(save_dir, f'{filename}.jpg')
                    
                    # Write the image content to file
                    content = await response.read()
                    with open(file_path, 'wb') as f:
                        f.write(content)
                    
                    # Store metadata
                    metadata[filename] = {
                        'url': url,
                        'timestamp': time.time(),
                        'content_type': response.headers.get('Content-Type', 'unknown'),
                        'file_path': file_path
                    }
                    
                    # Update progress counter
                    downloaded_count['value'] += 1
                    if downloaded_count['value'] % 100 == 0 or downloaded_count['value'] == total_images:
                        progress = downloaded_count['value'] / total_images * 100
                        self.logger.info(f"Downloaded {downloaded_count['value']} of {total_images} images ({progress:.1f}%)")
                    
                    return url
                    
                elif response.status == 404:
                    self.logger.warning(f"Image not found: {url}")
                    return None
                    
                else:
                    self.logger.warning(f"Failed to download {url}: HTTP {response.status}")
                    # Retry for server errors (5xx) and some client errors
                    if retry_count < self.retry_count and (response.status >= 500 or response.status == 429):
                        await asyncio.sleep(2 ** retry_count)  # Exponential backoff
                        return await self.download_image(session, url, save_dir, downloaded_count, total_images, metadata, retry_count + 1)
                    return None
                    
        except asyncio.TimeoutError:
            self.logger.warning(f"Timeout downloading {url}")
            if retry_count < self.retry_count:
                await asyncio.sleep(2 ** retry_count)  # Exponential backoff
                return await self.download_image(session, url, save_dir, downloaded_count, total_images, metadata, retry_count + 1)
            return None
            
        except Exception as e:
            self.logger.error(f"Error downloading {url}: {e}")
            return None
    
    async def download_images(self, image_urls, save_dir=None, batch_name=None):
        """
        Download multiple images asynchronously.
        
        Args:
            image_urls (list): List of image URLs to download.
            save_dir (str, optional): Directory to save images to. Uses config if not specified.
            batch_name (str, optional): Name for this batch of downloads.
            
        Returns:
            tuple: (successful_urls, failed_urls)
        """
        if not image_urls:
            self.logger.warning("No image URLs provided")
            return [], []
        
        # Use provided save_dir or create one based on batch_name
        if save_dir is None:
            if batch_name:
                save_dir = os.path.join(self.base_download_dir, batch_name)
            else:
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                save_dir = os.path.join(self.base_download_dir, f"batch_{timestamp}")
        
        # Ensure the save directory exists
        ensure_directory(save_dir)
        
        total_images = len(image_urls)
        downloaded_count = {'value': 0}
        metadata = {}
        successful_urls = []
        failed_urls = []
        
        self.logger.info(f"Starting download of {total_images} images to {save_dir}")
        start_time = time.time()
        
        # Create a semaphore to limit concurrent downloads
        semaphore = asyncio.Semaphore(self.concurrent_downloads)
        
        async def download_with_semaphore(url):
            async with semaphore:
                return await self.download_image(session, url, save_dir, downloaded_count, total_images, metadata)
        
        # Start downloads
        async with aiohttp.ClientSession() as session:
            tasks = [download_with_semaphore(url) for url in image_urls]
            results = await asyncio.gather(*tasks)
            
            # Process results
            for url, result in zip(image_urls, results):
                if result:
                    successful_urls.append(url)
                else:
                    failed_urls.append(url)
        
        # Save metadata to a file
        metadata_file = os.path.join(save_dir, 'metadata.json')
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=4)
        
        elapsed = time.time() - start_time
        download_rate = len(successful_urls) / elapsed if elapsed > 0 else 0
        
        self.logger.info(f"Download completed in {elapsed:.2f}s ({download_rate:.2f} images/s)")
        self.logger.info(f"Successfully downloaded {len(successful_urls)} images, failed: {len(failed_urls)}")
        
        # Save failed URLs to a file for potential retry
        if failed_urls:
            failed_file = os.path.join(save_dir, 'failed_urls.json')
            with open(failed_file, 'w') as f:
                json.dump(failed_urls, f, indent=4)
            self.logger.info(f"Failed URLs saved to {failed_file}")
        
        return successful_urls, failed_urls
    
    async def download_in_batches(self, image_urls, batch_size=1000, base_save_dir=None, batch_prefix="batch"):
        """
        Download images in batches to avoid memory issues with large lists.
        
        Args:
            image_urls (list): List of image URLs to download.
            batch_size (int): Number of images per batch.
            base_save_dir (str, optional): Base directory for all batches.
            batch_prefix (str): Prefix for batch folder names.
            
        Returns:
            dict: Statistics about the download process.
        """
        if not image_urls:
            self.logger.warning("No image URLs provided")
            return {"total": 0, "successful": 0, "failed": 0}
        
        # Set up base directory
        if base_save_dir is None:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            base_save_dir = os.path.join(self.base_download_dir, f"{batch_prefix}_{timestamp}")
        
        ensure_directory(base_save_dir)
        
        total_urls = len(image_urls)
        total_successful = 0
        total_failed = 0
        
        self.logger.info(f"Starting batch download of {total_urls} images")
        start_time = time.time()
        
        # Process in batches
        for i in range(0, total_urls, batch_size):
            batch_num = i // batch_size + 1
            end_idx = min(i + batch_size, total_urls)
            batch_urls = image_urls[i:end_idx]
            
            batch_dir = os.path.join(base_save_dir, f"{batch_prefix}_{batch_num}")
            
            self.logger.info(f"Processing batch {batch_num}: {len(batch_urls)} images")
            successful, failed = await self.download_images(batch_urls, save_dir=batch_dir)
            
            total_successful += len(successful)
            total_failed += len(failed)
            
            self.logger.info(f"Batch {batch_num} complete: {len(successful)} successful, {len(failed)} failed")
        
        elapsed = time.time() - start_time
        download_rate = total_successful / elapsed if elapsed > 0 else 0
        
        stats = {
            "total": total_urls,
            "successful": total_successful,
            "failed": total_failed,
            "elapsed_seconds": elapsed,
            "images_per_second": download_rate
        }
        
        self.logger.info(f"All batches complete in {elapsed:.2f}s ({download_rate:.2f} images/s)")
        self.logger.info(f"Total: {total_successful} successful, {total_failed} failed")
        
        # Save overall stats
        stats_file = os.path.join(base_save_dir, 'download_stats.json')
        with open(stats_file, 'w') as f:
            json.dump(stats, f, indent=4)
        
        return stats

def download_images(image_urls, save_dir=None, batch_size=None):
    """
    Download images from a list of URLs.
    
    Args:
        image_urls (list): List of image URLs to download.
        save_dir (str, optional): Directory to save images to.
        batch_size (int, optional): Size of batches if processing in batches.
        
    Returns:
        dict: Statistics about the download process.
    """
    downloader = ImageDownloader()
    
    if batch_size and batch_size < len(image_urls):
        return asyncio.run(downloader.download_in_batches(image_urls, batch_size, save_dir))
    else:
        successful, failed = asyncio.run(downloader.download_images(image_urls, save_dir))
        return {
            "total": len(image_urls),
            "successful": len(successful),
            "failed": len(failed)
        }
