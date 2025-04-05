import argparse
import asyncio
import os
import sys
import logging
from .crawler import WebCrawler
from .downloader import ImageDownloader
from .utils import ensure_directory, get_image_urls_from_json
from utils.logger import get_logger, setup_logger
from utils.config import Config

logger = None

async def scrape_and_download(start_url, max_pages=None, batch_size=1000, skip_crawl=False, skip_download=False):
    """
    Main function to scrape a website and download images.
    
    Args:
        start_url (str): URL to start crawling from.
        max_pages (int, optional): Maximum number of pages to crawl.
        batch_size (int): Number of images to download in one batch.
        skip_crawl (bool): Skip the crawling phase and use existing state file.
        skip_download (bool): Skip the download phase.
        
    Returns:
        tuple: (image_urls, download_stats)
    """
    config = Config()
    state_file = config.get('Scraper', 'StateFile', fallback='crawler_state.json')
    
    # Step 1: Crawl the website to find image URLs
    image_urls = []
    
    if not skip_crawl:
        logger.info("Starting crawling phase")
        crawler = WebCrawler()
        image_urls = await crawler.crawl_domain(start_url, max_pages, state_file)
        logger.info(f"Crawling complete, found {len(image_urls)} images")
    else:
        logger.info("Skipping crawling phase, loading URLs from state file")
        image_urls = get_image_urls_from_json(state_file)
        logger.info(f"Loaded {len(image_urls)} image URLs from state file")
    
    # Step 2: Download the images
    download_stats = {"total": 0, "successful": 0, "failed": 0}
    
    if not skip_download and image_urls:
        logger.info("Starting download phase")
        downloader = ImageDownloader()
        
        # Create timestamped download directory
        download_dir = config.get('Paths', 'DownloadFolder', fallback='data/downloaded_images')
        ensure_directory(download_dir)
        
        # Download images in batches
        download_stats = await downloader.download_in_batches(
            image_urls, 
            batch_size=batch_size,
            base_save_dir=download_dir
        )
        
        logger.info(f"Download phase complete: {download_stats['successful']} of {download_stats['total']} images downloaded")
    elif skip_download:
        logger.info("Skipping download phase")
    
    return image_urls, download_stats

def main():
    """Command-line entry point for the scraper."""
    global logger
    
    # Set up argument parser
    parser = argparse.ArgumentParser(description='Web scraper for downloading images')
    parser.add_argument('--url', type=str, help='Starting URL for crawling')
    parser.add_argument('--max-pages', type=int, help='Maximum number of pages to crawl')
    parser.add_argument('--batch-size', type=int, default=1000, help='Batch size for downloading')
    parser.add_argument('--skip-crawl', action='store_true', help='Skip crawling and use existing state file')
    parser.add_argument('--skip-download', action='store_true', help='Skip downloading and only crawl')
    parser.add_argument('--log-level', type=str, default='INFO', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'], help='Logging level')
    
    args = parser.parse_args()
    
    # Set up logging
    logger = setup_logger('scraper', log_level=getattr(logging, args.log_level))
    
    # Load configuration
    config = Config()
    
    # Check if URL is provided or in config
    start_url = args.url or config.get('Scraper', 'StartURL', fallback=None)
    
    if not start_url and not args.skip_crawl:
        logger.error("No start URL provided. Use --url or set StartURL in config.ini")
        sys.exit(1)
    
    # Run the scraper
    try:
        asyncio.run(scrape_and_download(
            start_url=start_url,
            max_pages=args.max_pages,
            batch_size=args.batch_size,
            skip_crawl=args.skip_crawl,
            skip_download=args.skip_download
        ))
    except KeyboardInterrupt:
        logger.info("Process interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"An error occurred: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()