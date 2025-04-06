from utils.logger import get_logger
from scraper.instagram_profile_finder import InstagramProfileFinder
from scraper.selenium_instagram_scraper import SeleniumInstagramScraper
from processing.face_encoder import FaceEncoder
import os
import time

class InstagramController:
    """Controls the Instagram profile discovery and scraping process."""
    
    def __init__(self, profiles_file="data/instagram_profiles.json", output_dir="data/downloaded_images/instagram"):
        self.logger = get_logger(__name__)
        self.profiles_file = profiles_file
        self.output_dir = output_dir
    
    async def run_full_pipeline(self, profile_count=200, max_profiles_to_scrape=5, max_images_per_profile=10):
        """Run the full Instagram pipeline: find profiles, scrape images, process faces."""
        start_time = time.time()
        self.logger.info("Starting Instagram profile pipeline")
        
        # Step 1: Find Instagram profiles
        self.logger.info(f"Finding Instagram profiles (target: {profile_count})...")
        finder = InstagramProfileFinder(output_file=self.profiles_file)
        profiles = await finder.run(target_count=profile_count, max_runtime_minutes=10)
        
        # Step 2: Scrape images from profiles using Selenium
        self.logger.info(f"Scraping images from {max_profiles_to_scrape} profiles (max {max_images_per_profile} per profile)...")
        
        # This is synchronous, not async
        scraper = SeleniumInstagramScraper(profiles_file=self.profiles_file, output_dir=self.output_dir)
        images = scraper.run(
            max_profiles=max_profiles_to_scrape,
            max_images_per_profile=max_images_per_profile
        )
        
        # Step 3: Process images for faces
        self.logger.info("Processing images for faces...")
        face_count = self._process_images(self.output_dir)
        
        # Report results
        elapsed = time.time() - start_time
        self.logger.info(f"Instagram pipeline completed in {elapsed/60:.2f} minutes")
        self.logger.info(f"Found {len(profiles)} profiles, scraped {len(images)} images, detected {face_count} faces")
        
        return {
            "profiles_found": len(profiles),
            "images_downloaded": len(images),
            "faces_detected": face_count,
            "runtime_seconds": elapsed
        }
    
    def _process_images(self, image_dir):
        """Process downloaded images to extract faces."""
        try:
            # Path to database folder
            from utils.config import Config
            config = Config()
            db_path = config.get('Paths', 'DatabaseFolder', fallback="data/database")
            cropped_face_folder = config.get('Paths', 'CroppedFaceFolder', fallback="data/cropped_faces")
            
            # Initialize face encoder
            face_encoder = FaceEncoder(
                img_folder=image_dir,
                db_path=db_path,
                cropped_face_folder=cropped_face_folder
            )
            
            # Process images with larger batch size and more workers
            face_count = face_encoder.encode_faces(batch_size=100, max_workers=8)
            return face_count
        except Exception as e:
            self.logger.error(f"Error processing images: {e}")
            return 0