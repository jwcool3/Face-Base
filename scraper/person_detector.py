import cv2
import numpy as np
import asyncio
from utils.logger import get_logger

class RealPersonDetector:
    """Analyzes images to determine if they likely contain real people vs stock photos."""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        # Load OpenCV face detector
        try:
            self.face_detector = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
            if self.face_detector.empty():
                self.logger.error("Failed to load face detector. Using fallback approach.")
                self.face_detector = None
        except Exception as e:
            self.logger.error(f"Error loading face detector: {e}")
            self.face_detector = None
        
    async def is_likely_real_person(self, image_url, session):
        """Checks if an image likely contains a real person (not stock or AI-generated)."""
        try:
            async with session.get(image_url, timeout=5) as response:
                if response.status != 200:
                    return False
                
                # Check content type
                content_type = response.headers.get('Content-Type', '')
                if not content_type.startswith('image/'):
                    return False
                
                # Load and process the image
                image_data = await response.read()
                
                # Convert to OpenCV format
                nparr = np.frombuffer(image_data, np.uint8)
                img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                
                if img is None:
                    return False
                
                # Check image size and quality
                height, width = img.shape[:2]
                
                # Skip tiny or huge images
                if height < 200 or width < 200 or height > 4000 or width > 4000:
                    return False
                
                # Quick check for image quality (too small/low quality isn't useful)
                if height * width < 100000:  # e.g., 316x316 or smaller
                    return False
                
                # Detect faces if face detector is available
                if self.face_detector is not None:
                    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                    faces = self.face_detector.detectMultiScale(gray, 1.3, 5)
                    
                    if len(faces) == 0:
                        return False
                    
                    # Check face size relative to image
                    for (x, y, w, h) in faces:
                        face_area = w * h
                        image_area = height * width
                        face_ratio = face_area / image_area
                        
                        # Face should be significant but not the entire image
                        if face_ratio < 0.02 or face_ratio > 0.9:
                            continue
                        
                        # This looks like a good face image
                        return True
                
                # Fallback if face detector failed: Check color distribution
                # Real photos often have more varied color distribution
                color_std = np.std(img.reshape(-1, 3), axis=0).mean()
                
                # Convert to grayscale for brightness check
                if len(img.shape) == 3:
                    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                else:
                    gray = img
                
                brightness = np.mean(gray)
                contrast = np.std(gray)
                
                # Characteristics of natural photos vs stock/generated
                is_natural = (
                    color_std > 30 and         # Good color variation
                    brightness > 50 and        # Not too dark
                    brightness < 200 and       # Not too bright
                    contrast > 40              # Decent contrast
                )
                
                return is_natural
                
        except asyncio.TimeoutError:
            self.logger.debug(f"Timeout checking image {image_url}")
            return False
        except Exception as e:
            self.logger.debug(f"Error checking image {image_url}: {e}")
            return False