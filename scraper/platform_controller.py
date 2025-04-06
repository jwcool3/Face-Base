import os
import time
import json
import logging
from typing import List, Dict, Optional
from utils.logger import get_logger
from processing.face_encoder import FaceEncoder
from utils.config import Config

class PlatformScrapeController:
    """
    Base controller for social media platform scraping.
    Provides a standardized pipeline for profile discovery, image scraping, and face processing.
    """
    
    def __init__(
        self, 
        platform_name: str,
        profiles_file: Optional[str] = None,
        output_dir: Optional[str] = None
    ):
        """
        Initialize the platform scrape controller.
        
        Args:
            platform_name (str): Name of the social media platform
            profiles_file (str, optional): Path to store discovered profiles
            output_dir (str, optional): Directory to save downloaded images
        """
        # Logger setup
        self.logger = get_logger(__name__)
        
        # Configuration
        self.config = Config()
        self.platform_name = platform_name
        
        # Default paths if not provided
        if profiles_file is None:
            profiles_file = f"data/{platform_name.lower()}_profiles.json"
        
        if output_dir is None:
            output_dir = os.path.join(
                self.config.get('Paths', 'DownloadFolder', fallback='data/downloaded_images'), 
                platform_name.lower()
            )
        
        # Ensure directories exist
        os.makedirs(os.path.dirname(profiles_file), exist_ok=True)
        os.makedirs(output_dir, exist_ok=True)
        
        self.profiles_file = profiles_file
        self.output_dir = output_dir
        
        # Profiles storage
        self.profiles = []
    
    def _load_profiles(self) -> List[str]:
        """
        Load previously discovered profiles from file.
        
        Returns:
            List[str]: List of discovered profiles
        """
        try:
            if os.path.exists(self.profiles_file):
                with open(self.profiles_file, 'r') as f:
                    data = json.load(f)
                    profiles = data.get('profiles', [])
                    self.logger.info(f"Loaded {len(profiles)} {self.platform_name} profiles")
                    return profiles
        except Exception as e:
            self.logger.error(f"Error loading {self.platform_name} profiles: {e}")
        
        return []
    
    def _save_profiles(self, profiles: List[str]):
        """
        Save discovered profiles to file.
        
        Args:
            profiles (List[str]): List of profiles to save
        """
        try:
            data = {
                'platform': self.platform_name,
                'profiles': profiles,
                'last_updated': time.strftime("%Y-%m-%d %H:%M:%S"),
                'count': len(profiles)
            }
            
            with open(self.profiles_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            self.logger.info(f"Saved {len(profiles)} {self.platform_name} profiles")
        except Exception as e:
            self.logger.error(f"Error saving {self.platform_name} profiles: {e}")
    
    def _process_images(self, image_dir: str) -> int:
        """
        Process images to extract face embeddings.
        
        Args:
            image_dir (str): Directory containing images to process
        
        Returns:
            int: Number of faces processed and added to database
        """
        try:
            # Get database and cropped face folders from config
            db_path = self.config.get('Paths', 'DatabaseFolder', fallback='data/database')
            cropped_face_folder = self.config.get('Paths', 'CroppedFaceFolder', fallback='data/cropped_faces')
            
            # Initialize face encoder
            face_encoder = FaceEncoder(
                img_folder=image_dir, 
                db_path=db_path, 
                cropped_face_folder=cropped_face_folder
            )
            
            # Process images
            face_count = face_encoder.encode_faces(batch_size=100, max_workers=8)
            
            self.logger.info(f"Processed {face_count} faces from {self.platform_name} images")
            return face_count
        
        except Exception as e:
            self.logger.error(f"Error processing {self.platform_name} images: {e}")
            return 0
    
    async def find_profiles(self, target_count: int = 200, max_runtime_minutes: int = 30) -> List[str]:
        """
        Find potential profiles to scrape.
        This method should be overridden by subclasses.
        
        Args:
            target_count (int): Number of profiles to find
            max_runtime_minutes (int): Maximum runtime for profile discovery
        
        Returns:
            List[str]: List of discovered profiles
        """
        raise NotImplementedError("Subclasses must implement profile discovery method")
    
    async def scrape_images(
        self, 
        max_profiles: int = 5, 
        max_images_per_profile: int = 10
    ) -> List[str]:
        """
        Scrape images from discovered profiles.
        This method should be overridden by subclasses.
        
        Args:
            max_profiles (int): Maximum number of profiles to scrape
            max_images_per_profile (int): Maximum images to download per profile
        
        Returns:
            List[str]: Paths to downloaded images
        """
        raise NotImplementedError("Subclasses must implement image scraping method")
    
    async def run_full_pipeline(
        self, 
        profile_count: int = 200, 
        max_profiles_to_scrape: int = 5, 
        max_images_per_profile: int = 10
    ) -> Dict[str, int]:
        """
        Run the complete scraping pipeline.
        Discovers profiles, scrapes images, and processes them.
        
        Args:
            profile_count (int): Number of profiles to find
            max_profiles_to_scrape (int): Maximum profiles to scrape
            max_images_per_profile (int): Maximum images to download per profile
        
        Returns:
            Dict[str, int]: Statistics about the scraping process
        """
        start_time = time.time()
        
        # Step 1: Find profiles
        self.logger.info(f"Finding {self.platform_name} profiles (target: {profile_count})...")
        profiles = await self.find_profiles(target_count=profile_count)
        self._save_profiles(profiles)
        
        # Step 2: Scrape images
        self.logger.info(f"Scraping images from {max_profiles_to_scrape} {self.platform_name} profiles...")
        images = await self.scrape_images(
            max_profiles=max_profiles_to_scrape,
            max_images_per_profile=max_images_per_profile
        )
        
        # Step 3: Process images for faces
        self.logger.info("Processing scraped images for faces...")
        faces_detected = self._process_images(self.output_dir)
        
        # Calculate elapsed time
        elapsed = time.time() - start_time
        
        # Prepare and log results
        results = {
            "platform": self.platform_name,
            "profiles_found": len(profiles),
            "profiles_scraped": min(max_profiles_to_scrape, len(profiles)),
            "images_downloaded": len(images),
            "faces_detected": faces_detected,
            "runtime_seconds": elapsed
        }
        
        self.logger.info(f"{self.platform_name} scraping pipeline completed in {elapsed/60:.2f} minutes")
        for key, value in results.items():
            self.logger.info(f"{key.replace('_', ' ').title()}: {value}")
        
        return results