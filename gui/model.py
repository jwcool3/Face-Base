import os
import numpy as np
from processing.face_matcher import FaceMatcher
from processing.face_detector import FaceDetector
from utils.config import Config
from utils.logger import get_logger
import json

class FaceMatcherModel:
    """
    Model component of the MVC architecture for the Face Matcher application.
    Handles data processing and business logic.
    """
    
    def __init__(self):
        """Initialize the model with configuration and components."""
        self.logger = get_logger(__name__)
        self.config = Config()
        
        # Initialize the face detector
        self.face_detector = FaceDetector()
        
        # Initialize the database path from config
        self.db_folder = self.config.get('Paths', 'DatabaseFolder')
        
        # Initialize the face matcher
        self.face_matcher = FaceMatcher(self.db_folder)
        
        # Initialize state variables
        self.current_image_path = None
        self.current_face_encoding = None
        self.current_face_age = None
        self.current_face_gender = None
        self.current_face_pose = None
        self.match_results = []
        self.current_match_index = 0
        
        # Initialize pose filter state
        self.pose_filter_enabled = False
        self.forward_facing_filter_enabled = False
        self.landmarks_overlay_enabled = False
        self.age_gender_overlay_enabled = True
        
        # Initialize landmarks
        self.landmarks_2d = None
    
    def get_database_size(self):
        """
        Get the number of faces in the database.
        
        Returns:
            int: Number of faces in the database.
        """
        return len(self.face_matcher.face_db)
    
    def process_image(self, image_path):
        """
        Process an image to detect faces and extract features.
        
        Args:
            image_path (str): Path to the image file.
            
        Returns:
            bool: True if a face was successfully detected and processed.
        """
        self.logger.info(f"Processing image: {image_path}")
        
        # Reset current state
        self.current_image_path = image_path
        self.current_face_encoding = None
        self.current_face_age = None
        self.current_face_gender = None
        self.current_face_pose = None
        self.landmarks_2d = None
        
        try:
            # Load and process the image
            image, faces = self.face_detector.process_image(image_path)
            
            if not faces:
                self.logger.warning(f"No faces detected in {image_path}")
                return False
                
            # Use the largest face
            face = self.face_detector.get_largest_face(faces)
            
            if face is None:
                self.logger.warning(f"No valid face found in {image_path}")
                return False
                
            # Extract face information
            face_info = self.face_detector.extract_face_info(face)
            
            # Store face data
            self.current_face_encoding = face_info['face_embedding']
            self.current_face_age = face_info['age']
            self.current_face_gender = face_info['gender']
            self.current_face_pose = face_info['pose']
            
            # Store landmarks if available
            if 'landmark_2d_106' in face_info:
                self.landmarks_2d = face_info['landmark_2d_106']
            elif 'landmark_3d_68' in face_info:
                # Convert 3D landmarks to 2D by ignoring Z coordinate
                self.landmarks_2d = [(x, y) for x, y, _ in face_info['landmark_3d_68']]
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error processing image {image_path}: {e}")
            return False
    
    def match_face(self):
        """
        Match the current face against the database.
        
        Returns:
            bool: True if matching was successful.
        """
        if self.current_face_encoding is None:
            self.logger.warning("No face encoding available for matching")
            return False
            
        try:
            # Match face based on filter settings
            if self.pose_filter_enabled and self.current_face_pose:
                self.match_results = self.face_matcher.filter_by_pose(
                    self.current_face_encoding, 
                    self.current_face_pose
                )
            elif self.forward_facing_filter_enabled:
                self.match_results = self.face_matcher.filter_forward_facing(
                    self.current_face_encoding
                )
            else:
                self.match_results = self.face_matcher.match_face(
                    self.current_face_encoding
                )
            
            # Reset the match index
            self.current_match_index = 0
            
            return len(self.match_results) > 0
            
        except Exception as e:
            self.logger.error(f"Error matching face: {e}")
            return False
    
    def get_current_match(self):
        """
        Get the current match result.
        
        Returns:
            tuple: (similarity_score, face_data) or None if no match.
        """
        if not self.match_results or self.current_match_index >= len(self.match_results):
            return None
            
        return self.match_results[self.current_match_index]
    
    def has_previous_match(self):
        """
        Check if there is a previous match result.
        
        Returns:
            bool: True if there is a previous match.
        """
        return self.current_match_index > 0
    
    def has_next_match(self):
        """
        Check if there is a next match result.
        
        Returns:
            bool: True if there is a next match.
        """
        return self.current_match_index < len(self.match_results) - 1
    
    def previous_match(self):
        """
        Go to the previous match result.
        
        Returns:
            tuple: (similarity_score, face_data) or None if no previous match.
        """
        if self.has_previous_match():
            self.current_match_index -= 1
            return self.get_current_match()
        return None
    
    def next_match(self):
        """
        Go to the next match result.
        
        Returns:
            tuple: (similarity_score, face_data) or None if no next match.
        """
        if self.has_next_match():
            self.current_match_index += 1
            return self.get_current_match()
        return None
    
    def toggle_pose_filter(self):
        """
        Toggle the pose filter state.
        
        Returns:
            bool: The new state of the pose filter.
        """
        self.pose_filter_enabled = not self.pose_filter_enabled
        if self.pose_filter_enabled:
            # Disable forward-facing filter if pose filter is enabled
            self.forward_facing_filter_enabled = False
        return self.pose_filter_enabled
    
    def toggle_forward_facing_filter(self):
        """
        Toggle the forward-facing filter state.
        
        Returns:
            bool: The new state of the forward-facing filter.
        """
        self.forward_facing_filter_enabled = not self.forward_facing_filter_enabled
        if self.forward_facing_filter_enabled:
            # Disable pose filter if forward-facing filter is enabled
            self.pose_filter_enabled = False
        return self.forward_facing_filter_enabled
    
    def toggle_landmarks_overlay(self):
        """
        Toggle the landmarks overlay state.
        
        Returns:
            bool: The new state of the landmarks overlay.
        """
        self.landmarks_overlay_enabled = not self.landmarks_overlay_enabled
        return self.landmarks_overlay_enabled
    
    def toggle_age_gender_overlay(self):
        """
        Toggle the age and gender overlay state.
        
        Returns:
            bool: The new state of the age and gender overlay.
        """
        self.age_gender_overlay_enabled = not self.age_gender_overlay_enabled
        return self.age_gender_overlay_enabled
