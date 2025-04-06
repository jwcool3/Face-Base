import os
import time
import asyncio
import random
from utils.logger import get_logger
from utils.config import Config
from scraper.social_media_target import SocialMediaTargetSelector
from scraper.social_media_crawler import SocialMediaCrawler
from scraper.downloader import ImageDownloader

class AutomaticPersonScraper:
    """
    Automatic scraper focused on finding public photos of real people from social media.
    """
    
    def __init__(self, db_path, download_dir, target_selector=None):
        self.logger = get_logger(__name__)
        self.target_selector = target_selector or SocialMediaTargetSelector()
        self.crawler = SocialMediaCrawler()
        self.downloader = ImageDownloader()
        self.db_path = db_path
        self.download_dir = download_dir
        
        # Configure parameters
        self.config = Config()
        self.max_pages_per_target = 20
        self.max_images_per_target = 250  # Increased from 100
        
        # Initialize the face detector once
        from processing.face_detector import FaceDetector
        self.face_detector = FaceDetector()
        
        # Reused face encoder to avoid reinitializing
        self.face_encoder = None
        
        # Ensure download directory exists
        os.makedirs(self.download_dir, exist_ok=True)
        
    async def run_automatic_mode(self, target_face_count=500, max_runtime_minutes=60):
        """
        Run automatic scraping until target face count is reached or time limit is hit.
        
        Args:
            target_face_count: Target number of face images to collect
            max_runtime_minutes: Maximum runtime in minutes
            
        Returns:
            dict: Statistics about the scraping operation
        """
        self.logger.info(f"Starting automatic person scraping. Target: {target_face_count} faces")
        
        max_runtime = max_runtime_minutes * 60  # Convert to seconds
        start_time = time.time()
        end_time = start_time + max_runtime
        
        face_count = 0
        sites_visited = 0
        total_images_processed = 0
        failed_sites = 0
        
        # Initialize a larger download batch size
        download_batch_size = 500  # Increased from default
        
        while face_count < target_face_count and time.time() < end_time:
            # Get next target
            target_url = self.target_selector.get_next_target()
            
            # Check if we got a valid target URL
            if target_url is None:
                self.logger.error("No valid target URLs available. Please check source selection.")
                break
                
            sites_visited += 1
            
            self.logger.info(f"Processing target {sites_visited}: {target_url}")
            
            # Create batch folder
            batch_name = f"social_{int(time.time())}"
            batch_dir = os.path.join(self.download_dir, batch_name)
            
            try:
                # Crawl the target for images 
                image_urls = await self.crawler.crawl_social_media(
                    target_url,
                    max_pages=self.max_pages_per_target,
                    max_images=self.max_images_per_target
                )
                
                if not image_urls:
                    self.logger.warning(f"No suitable images found at {target_url}")
                    failed_sites += 1
                    continue
                
                # Download the images with larger batch size
                self.logger.info(f"Downloading {len(image_urls)} images to {batch_dir}")
                self.downloader.concurrent_downloads = download_batch_size
                successful_urls, _ = await self.downloader.download_images(image_urls, batch_dir)
                
                # Process the images to extract faces with reused detector
                batch_face_count = await self.process_images(batch_dir)
                
                # Update counters
                face_count += batch_face_count
                total_images_processed += len(successful_urls)
                
                self.logger.info(f"Found {batch_face_count} faces in {len(successful_urls)} images from {target_url}")
                self.logger.info(f"Total progress: {face_count}/{target_face_count} faces")
                
                # Add a small delay between targets
                await asyncio.sleep(1)  # Reduced from 2 for faster operation
                
            except Exception as e:
                self.logger.error(f"Error processing {target_url}: {e}")
                failed_sites += 1
                continue
            
            # Check if we've reached our time limit
            if time.time() >= end_time:
                self.logger.info("Time limit reached. Stopping automatic mode.")
                break
        
        total_runtime = time.time() - start_time
        self.logger.info(f"Automatic scraping complete. Runtime: {total_runtime/60:.2f} minutes")
        self.logger.info(f"Collected {face_count} faces from {sites_visited} sites ({failed_sites} failed)")
        self.logger.info(f"Processed {total_images_processed} images")
        
        return {
            "face_count": face_count,
            "sites_visited": sites_visited,
            "images_processed": total_images_processed,
            "failed_sites": failed_sites,
            "runtime_seconds": total_runtime,
            "current_source": "Completed"
        }
    
    async def process_images(self, image_dir):
        """Process downloaded images to extract face embeddings."""
        # Process in a separate thread to avoid blocking the event loop
        loop = asyncio.get_event_loop()
        face_count = await loop.run_in_executor(
            None, 
            lambda: self._process_images_sync(image_dir)
        )
        
        return face_count
    
    def _process_images_sync(self, image_dir):
        """Synchronous image processing (runs in thread pool)."""
        try:
            # Use cached encoder if it exists, otherwise create one
            if self.face_encoder is None:
                # Import modules here to avoid circular imports
                from processing.face_encoder import FaceEncoder
                
                # Create a custom FaceEncoder class that reuses the detector
                class OptimizedFaceEncoder(FaceEncoder):
                    def __init__(self, img_folder, db_path, cropped_face_folder, face_detector):
                        super().__init__(img_folder, db_path, cropped_face_folder)
                        # Replace the detector with our pre-initialized one
                        if face_detector:
                            self.face_detector = face_detector
                            self.logger.info("Using pre-initialized face detector")
                
                # Create and cache the encoder
                self.face_encoder = OptimizedFaceEncoder(
                    img_folder=image_dir,
                    db_path=self.db_path,
                    cropped_face_folder=os.path.join(self.db_path, "../cropped_faces"),
                    face_detector=self.face_detector
                )
                self.logger.info("Created new optimized face encoder")
            else:
                # Update the image folder for the existing encoder
                self.face_encoder.img_folder = image_dir
                self.logger.info("Reusing existing face encoder")
            
            # Process images in the directory with larger batch size and more workers
            # Increase batch size and workers for better performance
            face_count = self.face_encoder.encode_faces(batch_size=250, max_workers=12)
            return face_count
            
        except Exception as e:
            self.logger.error(f"Error processing images in {image_dir}: {e}")
            return 0
            
    async def process_single_target(self, target_url, max_pages=20, max_images=250):
        """
        Process a single target URL and return statistics.
        This is useful for UI updates during automatic mode.
        
        Returns:
            tuple: (face_count, image_count, success_rate)
        """
        batch_name = f"social_{int(time.time())}"
        batch_dir = os.path.join(self.download_dir, batch_name)
        
        try:
            # Crawl the target
            image_urls = await self.crawler.crawl_social_media(
                target_url,
                max_pages=max_pages,
                max_images=max_images
            )
            
            if not image_urls:
                return 0, 0, 0
                
            # Download images with increased concurrency
            self.downloader.concurrent_downloads = 500
            successful_urls, failed_urls = await self.downloader.download_images(image_urls, batch_dir)
            
            # Process images (reusing the face encoder instance)
            face_count = await self.process_images(batch_dir)
            
            # Calculate success rate (0-1)
            if len(image_urls) > 0:
                success_rate = len(successful_urls) / len(image_urls)
            else:
                success_rate = 0
                
            return face_count, len(successful_urls), success_rate
            
        except Exception as e:
            self.logger.error(f"Error processing target {target_url}: {e}")
            return 0, 0, 0