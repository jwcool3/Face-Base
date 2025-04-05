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

async def scrape_and_download(start_url, max_pages=None, max_images=None, batch_size=1000, 
                             download_dir=None, skip_crawl=False, skip_download=False):
    """
    Main function to scrape a website and download images.
    
    Args:
        start_url (str): URL to start crawling from.
        max_pages (int, optional): Maximum number of pages to crawl.
        max_images (int, optional): Maximum number of images to download.
        batch_size (int): Number of images to download in one batch.
        download_dir (str, optional): Directory to save images to.
        skip_crawl (bool): Skip the crawling phase and use existing state file.
        skip_download (bool): Skip the download phase.
        
    Returns:
        tuple: (image_urls, download_stats)
    """
    logger = get_logger(__name__)
    config = Config()
    
    # Set up paths
    if download_dir is None:
        download_dir = config.get('Paths', 'DownloadFolder', fallback='data/downloaded_images')
    
    state_file = config.get('Scraper', 'StateFile', fallback='data/crawler_state.json')
    
    # Ensure directories exist
    ensure_directory(os.path.dirname(state_file))
    ensure_directory(download_dir)
    
    # Step 1: Crawl the website to find image URLs
    image_urls = []
    
    if not skip_crawl:
        logger.info("Starting crawling phase")
        crawler = WebCrawler()
        image_urls = await crawler.crawl_domain(start_url, max_pages, state_file)
        logger.info(f"Crawling complete, found {len(image_urls)} images")
        
        # Limit to max_images if specified
        if max_images and len(image_urls) > max_images:
            logger.info(f"Limiting to {max_images} images")
            image_urls = list(image_urls)[:max_images]
    else:
        logger.info("Skipping crawling phase, loading URLs from state file")
        image_urls = get_image_urls_from_json(state_file)
        logger.info(f"Loaded {len(image_urls)} image URLs from state file")
        
        # Limit to max_images if specified
        if max_images and len(image_urls) > max_images:
            logger.info(f"Limiting to {max_images} images")
            image_urls = list(image_urls)[:max_images]
    
    # Step 2: Download the images
    download_stats = {"total": 0, "successful": 0, "failed": 0}
    
    if not skip_download and image_urls:
        logger.info("Starting download phase")
        downloader = ImageDownloader()
        
        # Convert image_urls to list if it's a set
        if isinstance(image_urls, set):
            image_urls = list(image_urls)
        
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
    # Set up argument parser
    parser = argparse.ArgumentParser(description='Web scraper for downloading images')
    parser.add_argument('--url', type=str, help='Starting URL for crawling')
    parser.add_argument('--max-pages', type=int, help='Maximum number of pages to crawl')
    parser.add_argument('--max-images', type=int, help='Maximum number of images to download')
    parser.add_argument('--batch-size', type=int, default=1000, help='Batch size for downloading')
    parser.add_argument('--output-dir', type=str, help='Directory to save downloaded images')
    parser.add_argument('--skip-crawl', action='store_true', help='Skip crawling and use existing state file')
    parser.add_argument('--skip-download', action='store_true', help='Skip downloading and only crawl')
    parser.add_argument('--process', action='store_true', help='Process downloaded images after download')
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
    
    # Set output directory
    output_dir = args.output_dir or config.get('Paths', 'DownloadFolder', fallback='data/downloaded_images')
    
    # Run the scraper
    try:
        image_urls, stats = asyncio.run(scrape_and_download(
            start_url=start_url,
            max_pages=args.max_pages,
            max_images=args.max_images,
            batch_size=args.batch_size,
            download_dir=output_dir,
            skip_crawl=args.skip_crawl,
            skip_download=args.skip_download
        ))
        
        # Print stats
        print(f"\nScraping results:")
        print(f"Images found: {len(image_urls)}")
        print(f"Downloaded: {stats.get('successful', 0)} of {stats.get('total', 0)}")
        print(f"Failed: {stats.get('failed', 0)}")
        print(f"Download directory: {output_dir}")
        
        # Process images if requested
        if args.process and not args.skip_download and stats.get('successful', 0) > 0:
            logger.info("Processing downloaded images...")
            
            # Import here to avoid circular imports
            from processing.face_encoder import FaceEncoder
            
            # Get paths from config
            db_path = config.get('Paths', 'DatabaseFolder', fallback='data/database')
            cropped_face_folder = config.get('Paths', 'CroppedFaceFolder', fallback='data/cropped_faces')
            
            # Initialize face encoder
            face_encoder = FaceEncoder(output_dir, db_path, cropped_face_folder)
            
            # Process images
            face_count = face_encoder.encode_faces()
            logger.info(f"Processing complete. Encoded {face_count} faces.")
            
            print(f"Faces processed and added to database: {face_count}")
        
    except KeyboardInterrupt:
        logger.info("Process interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"An error occurred: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()