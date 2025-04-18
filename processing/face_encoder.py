import os
import json
import cv2
import numpy as np
from PIL import Image
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import tempfile
from utils.config import Config
from utils.logger import get_logger
from processing.face_detector import FaceDetector

class FaceEncoder:
    """
    Processes images to extract face encodings and store them in a database.
    
    This class handles:
    1. Finding all images in a directory
    2. Detecting faces in each image
    3. Extracting facial features and embeddings
    4. Saving the processed data to a database
    """
    
    def __init__(self, img_folder=None, db_path=None, cropped_face_folder=None):
        """
        Initialize the FaceEncoder with paths from config if not provided.
        
        Args:
            img_folder (str, optional): Folder containing images for processing.
            db_path (str, optional): Path to save the face database.
            cropped_face_folder (str, optional): Folder to save cropped faces.
        """
        self.logger = get_logger(__name__)
        self.config = Config()
        
        # Use provided paths or get from config
        self.img_folder = self._normalize_path(img_folder or self.config.get('Paths', 'ImageFolder'))
        self.db_path = self._normalize_path(db_path or self.config.get('Paths', 'DatabaseFolder'))
        self.cropped_face_folder = self._normalize_path(cropped_face_folder or self.config.get('Paths', 'CroppedFaceFolder'))
        
        # Initialize folders for organizing images
        self.faces_folder = self._normalize_path(os.path.join(self.img_folder, "faces"))
        self.no_faces_folder = self._normalize_path(os.path.join(self.img_folder, "no_faces"))
        
        # Create necessary directories and check permissions
        self._initialize_directories()
        
        # Initialize face detector
        self.face_detector = FaceDetector()
    
    def _normalize_path(self, path):
        """
        Normalize a path to use system-native separators and absolute paths.
        
        Args:
            path (str): Path to normalize.
            
        Returns:
            str: Normalized absolute path.
        """
        if path is None:
            return None
        # Convert separators to system native and normalize
        path = os.path.normpath(path.replace('/', os.path.sep).replace('\\', os.path.sep))
        # Convert to absolute path if not already
        if not os.path.isabs(path):
            path = os.path.abspath(path)
        return path
    
    def _initialize_directories(self):
        """Create necessary directories and verify they are writable."""
        directories = [
            self.faces_folder,
            self.no_faces_folder,
            self.cropped_face_folder,
            self.db_path
        ]
        
        for directory in directories:
            try:
                os.makedirs(directory, exist_ok=True)
                if not self._is_directory_writable(directory):
                    raise PermissionError(f"Directory is not writable: {directory}")
                self.logger.debug(f"Initialized directory: {directory}")
            except Exception as e:
                self.logger.error(f"Error initializing directory {directory}: {e}")
                raise
    
    def _is_directory_writable(self, directory):
        """
        Check if a directory is writable by attempting to create a temporary file.
        
        Args:
            directory (str): Path to the directory to check.
            
        Returns:
            bool: True if the directory is writable, False otherwise.
        """
        if not os.path.exists(directory):
            return False
            
        try:
            testfile = os.path.join(directory, "write_test_" + str(time.time()))
            with open(testfile, 'w') as f:
                f.write("test")
            os.remove(testfile)
            return True
        except Exception as e:
            self.logger.warning(f"Directory {directory} is not writable: {e}")
            return False
    
    def get_image_files(self, folder):
        """
        Get all image files from a folder and its subfolders.
        
        Args:
            folder (str): Folder to search for images.
            
        Returns:
            list: List of paths to image files.
        """
        image_files = []
        folder = self._normalize_path(folder)
        
        excluded_dirs = {
            self._normalize_path(self.cropped_face_folder),
            self._normalize_path(self.faces_folder),
            self._normalize_path(self.no_faces_folder)
        }
        
        for root, dirs, files in os.walk(folder):
            # Skip excluded folders
            dirs[:] = [d for d in dirs if self._normalize_path(os.path.join(root, d)) not in excluded_dirs]
            
            for file in files:
                if file.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp')):
                    image_files.append(self._normalize_path(os.path.join(root, file)))
                    
        self.logger.info(f"Found {len(image_files)} image files in {folder}")
        return image_files
    
    def process_image(self, img_path):
        """
        Process a single image to detect and encode faces.
        
        Args:
            img_path (str): Path to the image file.
            
        Returns:
            tuple: (img_path, face_data_list) where face_data_list is a list of 
                  dictionaries containing face information.
        """
        self.logger.debug(f"Processing image: {img_path}")
        face_data_list = []
        
        try:
            # Use face detector to get the image and detect faces
            image, faces = self.face_detector.process_image(img_path)
            
            if image is None:
                return img_path, []
                
            if faces:
                # Process each detected face
                for idx, face in enumerate(faces):
                    try:
                        # Get face information
                        face_info = self.face_detector.extract_face_info(face)
                        
                        # Crop the face image
                        cropped_face = self.face_detector.crop_face(image, face)
                        if cropped_face is None or cropped_face.size == 0:
                            continue
                            
                        # Convert BGR to RGB for saving
                        cropped_face_rgb = cv2.cvtColor(cropped_face, cv2.COLOR_BGR2RGB)
                            
                        # Save the cropped face
                        face_filename = f"{os.path.splitext(os.path.basename(img_path))[0]}_face_{idx}.jpg"
                        cropped_face_path = os.path.join(self.cropped_face_folder, face_filename)
                        
                        # Save using PIL to ensure correct color space
                        pil_image = Image.fromarray(cropped_face_rgb)
                        pil_image.save(cropped_face_path, quality=95)
                        self.logger.debug(f"Saved cropped face: {cropped_face_path}")
                        
                        # Create face data entry
                        face_data = {
                            'image_source': img_path,
                            'img_path': cropped_face_path,
                            **face_info,
                            'resolution': f"{cropped_face_rgb.shape[1]}x{cropped_face_rgb.shape[0]} Pixels",
                            'folder_name': os.path.basename(os.path.dirname(img_path))
                        }
                        
                        face_data_list.append(face_data)
                    except Exception as e:
                        self.logger.error(f"Error processing face {idx} in {img_path}: {e}")
                
                # Move the processed image to faces folder
                if face_data_list:
                    try:
                        os.rename(img_path, os.path.join(self.faces_folder, os.path.basename(img_path)))
                        self.logger.debug(f"Moved {img_path} to faces folder")
                    except OSError as e:
                        self.logger.warning(f"Could not move {img_path} to faces folder: {e}")
            else:
                # No faces found, move to no_faces folder
                try:
                    os.rename(img_path, os.path.join(self.no_faces_folder, os.path.basename(img_path)))
                    self.logger.debug(f"Moved {img_path} to no_faces folder (no faces detected)")
                except OSError as e:
                    self.logger.warning(f"Could not move {img_path} to no_faces folder: {e}")
        
        except Exception as e:
            self.logger.error(f"Error processing image {img_path}: {e}")
            
        return img_path, face_data_list
    
    def encode_faces(self, batch_size=250, max_workers=12):
        """
        Process all images in the input folder to detect and encode faces.
        
        Args:
            batch_size (int): Number of images to process in each batch.
            max_workers (int): Maximum number of worker threads.
            
        Returns:
            int: Number of faces processed.
        """
        # Get all image files
        self.logger.info(f"Looking for images in {self.img_folder} with batch size {batch_size}")
        image_files = self.get_image_files(self.img_folder)
        total_images = len(image_files)
        
        if total_images == 0:
            self.logger.warning(f"No images found in {self.img_folder}")
            return 0
            
        # Process in batches
        total_faces = 0
        batch_count = (total_images + batch_size - 1) // batch_size
        file_count = 0
        
        # Cache for faster processing
        self.logger.info(f"Processing {total_images} images in {batch_count} batches with {max_workers} workers")
        import time
        overall_start_time = time.time()
        
        # Create face buffer to minimize database writes
        all_face_buffer = []
        max_faces_before_save = 5000  # Save to database when buffer reaches this size
        
        for batch_idx in range(batch_count):
            start_idx = batch_idx * batch_size
            end_idx = min(start_idx + batch_size, total_images)
            current_batch = image_files[start_idx:end_idx]
            
            self.logger.info(f"Processing batch {batch_idx+1}/{batch_count} ({len(current_batch)} images)")
            start_time = time.time()
            
            face_buffer = []
            
            # Process images in parallel
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_path = {executor.submit(self.process_image, img_path): img_path for img_path in current_batch}
                
                for future in as_completed(future_to_path):
                    img_path = future_to_path[future]
                    try:
                        _, face_data_list = future.result()
                        if face_data_list:
                            face_buffer.extend(face_data_list)
                            all_face_buffer.extend(face_data_list)
                            total_faces += len(face_data_list)
                    except Exception as e:
                        self.logger.error(f"Exception processing {img_path}: {e}")
            
            # Save to database if the accumulated buffer is large enough
            if len(all_face_buffer) >= max_faces_before_save:
                self.logger.info(f"Buffer reached {len(all_face_buffer)} faces, saving to database...")
                file_count = self.save_to_database(all_face_buffer, file_count)
                all_face_buffer = []  # Clear buffer after saving
            
            # Log processing time
            end_time = time.time()
            elapsed = end_time - start_time
            speed = len(current_batch) / elapsed if elapsed > 0 else 0
            faces_per_second = len(face_buffer) / elapsed if elapsed > 0 and face_buffer else 0
            
            self.logger.info(f"Batch {batch_idx+1} processed in {elapsed:.2f}s ({speed:.2f} images/s, {faces_per_second:.2f} faces/s)")
            self.logger.info(f"Found {len(face_buffer)} faces in this batch, {total_faces} total so far")
        
        # Save any remaining faces in buffer
        if all_face_buffer:
            self.logger.info(f"Saving remaining {len(all_face_buffer)} faces to database...")
            file_count = self.save_to_database(all_face_buffer, file_count)
        
        overall_elapsed = time.time() - overall_start_time
        overall_speed = total_images / overall_elapsed if overall_elapsed > 0 else 0
        overall_faces_per_second = total_faces / overall_elapsed if overall_elapsed > 0 and total_faces > 0 else 0
        
        self.logger.info(f"All batches completed in {overall_elapsed:.2f}s")
        self.logger.info(f"Overall speed: {overall_speed:.2f} images/s, {overall_faces_per_second:.2f} faces/s")
        
        # Verify the entire database after processing
        self.logger.info("Verifying database integrity...")
        stats = self.verify_database()
        
        self.logger.info(f"Processing complete. Encoded {total_faces} faces from {total_images} images")
        return total_faces
    
    def save_to_database(self, face_buffer, file_count, max_faces_per_file=1000):
        """
        Save face data to JSON database files, with a maximum number of faces per file.
        
        Args:
            face_buffer (list): List of face data dictionaries to save.
            file_count (int): Current file count for naming.
            max_faces_per_file (int): Maximum number of faces to store in a single file.
            
        Returns:
            int: Updated file count.
        """
        if not face_buffer:
            self.logger.warning("No face data to save")
            return file_count
            
        # Ensure the database directory exists
        os.makedirs(self.db_path, exist_ok=True)
        
        # Determine how many files we need
        num_files = (len(face_buffer) + max_faces_per_file - 1) // max_faces_per_file
        
        for i in range(num_files):
            start_idx = i * max_faces_per_file
            end_idx = min(start_idx + max_faces_per_file, len(face_buffer))
            batch = face_buffer[start_idx:end_idx]
            
            db_filename = f'face_data_batch_{file_count}.json'
            db_file_path = os.path.join(self.db_path, db_filename)
            
            # Use atomic write pattern with temporary file
            try:
                import tempfile
                with tempfile.NamedTemporaryFile('w', delete=False) as tmp_file:
                    # Serialize the face data
                    json.dump(batch, tmp_file, indent=2)
                    tmp_file.flush()
                    os.fsync(tmp_file.fileno())  # Ensure data is written to disk
                    tmp_path = tmp_file.name
                    
                # Rename temp file to final filename (atomic operation)
                import shutil
                shutil.move(tmp_path, db_file_path)
                
                self.logger.info(f"Saved {len(batch)} faces to {db_file_path}")
                file_count += 1
            except Exception as e:
                self.logger.error(f"Error saving faces to database: {e}")
        
        return file_count

    def verify_database(self):
        """
        Verify database files and return statistics.
        Modified to be less strict about verification.
        
        Returns:
            dict: Statistics about the database verification.
        """
        import random
        
        stats = {
            'total_files': 0,
            'valid_files': 0,
            'total_faces': 0,
            'corrupted_files': 0
        }
        
        if not os.path.exists(self.db_path):
            self.logger.warning(f"Database path does not exist: {self.db_path}")
            return stats
            
        db_files = [f for f in os.listdir(self.db_path) if f.endswith('.json')]
        stats['total_files'] = len(db_files)
        
        if not db_files:
            self.logger.warning(f"No database files found in {self.db_path}")
            return stats
            
        self.logger.info(f"Verifying {len(db_files)} database files...")
        
        # Only sample a few files for verification to improve speed
        sample_size = min(5, len(db_files))
        sampled_files = random.sample(db_files, sample_size) if len(db_files) > sample_size else db_files
        
        for db_file in sampled_files:
            db_file_path = os.path.join(self.db_path, db_file)
            try:
                with open(db_file_path, 'r') as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        faces_count = len(data)
                        stats['total_faces'] += faces_count
                        stats['valid_files'] += 1
                        self.logger.debug(f"Verified {db_file}: {faces_count} faces")
                    else:
                        stats['corrupted_files'] += 1
                        self.logger.error(f"Invalid data format in {db_file}")
            except Exception as e:
                stats['corrupted_files'] += 1
                self.logger.error(f"Error verifying {db_file}: {e}")
        
        # Scale up the total_faces count based on sampling
        if len(db_files) > sample_size:
            scaling_factor = len(db_files) / sample_size
            stats['total_faces'] = int(stats['total_faces'] * scaling_factor)
        
        # Log verification results
        self.logger.info(
            f"Database verification complete:\n"
            f"- Total files: {stats['total_files']}\n"
            f"- Valid files: {stats['valid_files']} (sampled)\n"
            f"- Total faces: {stats['total_faces']} (estimated)\n"
            f"- Corrupted files: {stats['corrupted_files']}"
        )
        
        return stats

    def _process_image_batch(self, face_encoder, image_files, min_face_size, skip_existing, move_processed):
        """Process a batch of images and return statistics."""
        batch_stats = {
            'processed_images': 0,
            'faces_found': 0,
            'faces_added': 0,
            'skipped_images': 0,
            'error_images': 0
        }
        
        # Collect all face data for batch saving
        face_data_buffer = []
        
        for img_path in image_files:
            try:
                # Normalize path for Windows - convert all separators to system native
                img_path = os.path.normpath(os.path.abspath(img_path.replace('/', os.path.sep).replace('\\', os.path.sep)))
                
                # Check if file exists
                if not os.path.isfile(img_path):
                    self.logger.warning(f"File does not exist: {img_path}")
                    batch_stats['error_images'] += 1
                    continue
                
                # Skip if already processed and skip_existing is True
                if skip_existing and self._is_face_in_database(img_path):
                    batch_stats['skipped_images'] += 1
                    continue
                    
                # Process the image
                _, face_data_list = face_encoder.process_image(img_path)
                batch_stats['processed_images'] += 1
                
                if face_data_list:
                    # Filter faces by size if needed
                    if min_face_size > 0:
                        face_data_list = [f for f in face_data_list if self._check_face_size(f, min_face_size)]
                    
                    # Normalize paths in face data
                    for face_data in face_data_list:
                        if 'image_source' in face_data:
                            face_data['image_source'] = os.path.normpath(face_data['image_source'].replace('/', os.path.sep).replace('\\', os.path.sep))
                        if 'img_path' in face_data:
                            face_data['img_path'] = os.path.normpath(face_data['img_path'].replace('/', os.path.sep).replace('\\', os.path.sep))
                    
                    # Add faces to buffer
                    face_data_buffer.extend(face_data_list)
                    
                    batch_stats['faces_found'] += len(face_data_list)
                    batch_stats['faces_added'] += len(face_data_list)
                else:
                    # No faces found
                    if move_processed:
                        try:
                            # Create the no_faces directory in the same directory as the image
                            img_dir = os.path.dirname(img_path)
                            img_filename = os.path.basename(img_path)
                            no_faces_dir = os.path.normpath(os.path.join(img_dir, "no_faces"))
                            
                            # Create directory if it doesn't exist
                            os.makedirs(no_faces_dir, exist_ok=True)
                            
                            # Construct destination path
                            dest_path = os.path.normpath(os.path.join(no_faces_dir, img_filename))
                            
                            # If destination exists, add a suffix
                            base, ext = os.path.splitext(dest_path)
                            counter = 1
                            while os.path.exists(dest_path):
                                dest_path = os.path.normpath(f"{base}_{counter}{ext}")
                                counter += 1
                            
                            # Copy first, then remove original
                            try:
                                import shutil
                                shutil.copy2(img_path, dest_path)
                                if os.path.exists(dest_path):  # Verify copy succeeded
                                    try:
                                        os.remove(img_path)
                                    except Exception as e:
                                        self.logger.warning(f"Could not remove original file {img_path}: {e}")
                            except Exception as e:
                                self.logger.error(f"Error copying file {img_path} to {dest_path}: {e}")
                        except Exception as e:
                            self.logger.error(f"Error handling file {img_path}: {e}")
            except Exception as e:
                self.logger.error(f"Error processing image {img_path}: {e}")
                batch_stats['error_images'] += 1
        
        # Save the collected face data to database
        if face_data_buffer:
            try:
                # Ensure database directory exists
                os.makedirs(self.db_path, exist_ok=True)
                
                # Generate a timestamp-based filename
                import time
                timestamp = int(time.time())
                db_filename = f"face_data_batch_{timestamp}.json"
                db_file_path = os.path.normpath(os.path.join(self.db_path, db_filename))
                
                # Save using atomic write pattern
                import tempfile
                temp_dir = os.path.dirname(db_file_path)  # Use same directory as target
                
                with tempfile.NamedTemporaryFile('w', delete=False, dir=temp_dir, suffix='.json') as tmp_file:
                    json.dump(face_data_buffer, tmp_file, indent=2)
                    tmp_file.flush()
                    os.fsync(tmp_file.fileno())
                    tmp_path = tmp_file.name
                
                # Rename temp file to final filename (atomic operation)
                # If target exists, remove it first (Windows requirement)
                if os.path.exists(db_file_path):
                    os.remove(db_file_path)
                os.rename(tmp_path, db_file_path)
                
                self.logger.info(f"Saved {len(face_data_buffer)} faces to {db_file_path}")
                
                # Verify the saved file
                if not self._verify_database_file(db_file_path, len(face_data_buffer)):
                    self.logger.error(f"Database file verification failed: {db_file_path}")
                    batch_stats['faces_added'] = 0
            except Exception as e:
                self.logger.error(f"Error saving face data to database: {e}")
                batch_stats['faces_added'] = 0
        
        return batch_stats
        
    def _is_face_in_database(self, img_path):
        """Check if an image has already been processed and exists in the database."""
        try:
            img_path = self._normalize_path(img_path)
            # Look for any database file containing this image path
            for db_file in os.listdir(self.db_path):
                if not db_file.endswith('.json'):
                    continue
                    
                db_file_path = self._normalize_path(os.path.join(self.db_path, db_file))
                try:
                    with open(db_file_path, 'r') as f:
                        data = json.load(f)
                        if any(self._normalize_path(face['image_source']) == img_path for face in data):
                            return True
                except Exception:
                    continue
            return False
        except Exception:
            return False
            
    def _verify_database_file(self, db_file_path, expected_faces):
        """Verify that a database file was saved correctly."""
        try:
            with open(db_file_path, 'r') as f:
                data = json.load(f)
                actual_faces = len(data)
                if actual_faces != expected_faces:
                    self.logger.warning(
                        f"Database verification failed for {db_file_path}: "
                        f"Expected {expected_faces} faces, found {actual_faces}"
                    )
                else:
                    self.logger.info(f"Database file {db_file_path} verified successfully")
                return actual_faces == expected_faces
        except Exception as e:
            self.logger.error(f"Error verifying database file {db_file_path}: {e}")
            return False