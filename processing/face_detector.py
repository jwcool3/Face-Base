import cv2
import numpy as np
import insightface
from insightface.app import FaceAnalysis
import os
from utils.config import Config
from utils.logger import get_logger

class FaceDetectionError(Exception):
    """Base exception for face detection errors."""
    pass

class ModelInitializationError(FaceDetectionError):
    """Exception raised when the face detection model fails to initialize."""
    pass

class ImageReadError(FaceDetectionError):
    """Exception raised when an image cannot be read."""
    pass

class FaceDetector:
    """
    Handles face detection and analysis using InsightFace.
    
    This class provides methods to detect faces in images, extract facial
    landmarks, estimate age and gender, and process face embeddings.
    """
    
    def __init__(self):
        """Initialize the face detector with configuration settings."""
        self.logger = get_logger(__name__)
        self.config = Config()
        
        # Get configuration values
        self.det_threshold = self.config.getfloat('FaceDetection', 'DetectionThreshold', fallback=0.8)
        self.det_size = self.config.get_detection_size()
        self.ctx_id = self.config.get_gpu_id()
        
        self.logger.info(f"Initializing face detector with det_size={self.det_size}, threshold={self.det_threshold}, ctx_id={self.ctx_id}")
        
        try:
            self.model = FaceAnalysis()
            self.model.prepare(ctx_id=self.ctx_id, det_size=self.det_size, det_thresh=self.det_threshold)
            self.logger.info("Face detection model initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize face detection model: {e}")
            raise ModelInitializationError(f"Failed to initialize face detection model: {e}")
    
    def read_image(self, image_path):
        """
        Read an image from a file path.
        
        Args:
            image_path (str): Path to the image file.
            
        Returns:
            numpy.ndarray: The image as a numpy array.
            
        Raises:
            ImageReadError: If the image cannot be read.
        """
        try:
            image = cv2.imread(image_path)
            if image is None:
                raise ImageReadError(f"Image could not be read: {image_path}")
            return image
        except Exception as e:
            self.logger.error(f"Error reading image {image_path}: {e}")
            raise ImageReadError(f"Error reading image {image_path}: {e}")
    
    def detect_faces(self, image):
        """
        Detect faces in an image.
        
        Args:
            image (numpy.ndarray): Image as a numpy array.
            
        Returns:
            list: List of detected faces.
        """
        try:
            # Ensure image is in BGR format for InsightFace
            if len(image.shape) == 2:  # Grayscale
                image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
            elif image.shape[2] == 4:  # RGBA
                image = cv2.cvtColor(image, cv2.COLOR_RGBA2BGR)
                
            faces = self.model.get(image)
            self.logger.debug(f"Detected {len(faces)} faces")
            return faces
        except Exception as e:
            self.logger.error(f"Error detecting faces: {e}")
            return []
    
    def process_image(self, image_path):
        """
        Process an image file to detect faces and extract information.
        
        Args:
            image_path (str): Path to the image file.
            
        Returns:
            tuple: (image, faces) where image is the numpy array and
                  faces is a list of detected faces.
        """
        try:
            image = self.read_image(image_path)
            faces = self.detect_faces(image)
            return image, faces
        except ImageReadError as e:
            self.logger.warning(f"Skipping image: {e}")
            return None, []
        except Exception as e:
            self.logger.error(f"Unexpected error processing image {image_path}: {e}")
            return None, []
    
    def get_largest_face(self, faces):
        """
        Get the largest face from a list of detected faces.
        
        Args:
            faces (list): List of detected faces.
            
        Returns:
            object: The largest face, or None if no faces are detected.
        """
        if not faces:
            return None
            
        max_area = 0
        largest_face = None
        
        for face in faces:
            bbox = face.bbox.astype(int)
            area = (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])
            if area > max_area:
                max_area = area
                largest_face = face
                
        return largest_face
    
    def crop_face(self, image, face, margin=0.1):
        """
        Crop a face from an image with an optional margin.
        
        Args:
            image (numpy.ndarray): Image as a numpy array.
            face (object): Detected face.
            margin (float): Margin to add around the face (percentage of face size).
            
        Returns:
            numpy.ndarray: Cropped face image.
        """
        if face is None:
            return None
            
        h, w = image.shape[:2]
        bbox = face.bbox.astype(int)
        
        # Calculate margin in pixels
        x_margin = int((bbox[2] - bbox[0]) * margin)
        y_margin = int((bbox[3] - bbox[1]) * margin)
        
        # Apply margin with boundary checks
        left = max(0, bbox[0] - x_margin)
        top = max(0, bbox[1] - y_margin)
        right = min(w, bbox[2] + x_margin)
        bottom = min(h, bbox[3] + y_margin)
        
        # Crop the face
        cropped_face = image[top:bottom, left:right]
        return cropped_face
    
    def extract_face_info(self, face, include_embedding=True):
        """
        Extract information from a detected face.
        
        Args:
            face (object): Detected face.
            include_embedding (bool): Whether to include the face embedding.
            
        Returns:
            dict: Dictionary with face information.
        """
        info = {
            'bbox': face.bbox.astype(int).tolist(),
            'age': float(face.age),
            'gender': 'Female' if face.gender < 0.5 else 'Male',
            'pose': face.pose.tolist() if hasattr(face, 'pose') else None,
        }
        
        # Include landmark information if available
        if hasattr(face, 'landmark_3d_68'):
            info['landmark_3d_68'] = face.landmark_3d_68.tolist()
        if hasattr(face, 'landmark_2d_106'):
            info['landmark_2d_106'] = face.landmark_2d_106.tolist()
        
        # Include embedding if requested
        if include_embedding and hasattr(face, 'embedding'):
            info['face_embedding'] = face.embedding.tolist()
            
        return info
