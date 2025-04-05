import os
import json
import numpy as np
from scipy.spatial import distance
from scipy.spatial.distance import cosine
import time
from utils.config import Config
from utils.logger import get_logger

class FaceMatcher:
    """
    Matches face embeddings against a database of face embeddings.
    
    This class provides methods to:
    1. Load a database of face embeddings
    2. Match a target face against the database
    3. Filter matches based on criteria like pose
    """
    
    def __init__(self, db_folder=None):
        """
        Initialize the FaceMatcher with a database folder.
        
        Args:
            db_folder (str, optional): Path to the folder containing face database files.
        """
        self.logger = get_logger(__name__)
        self.config = Config()
        
        # Set up database path
        self.db_folder = db_folder or self.config.get('Paths', 'DatabaseFolder')
        self.similarity_threshold = self.config.getfloat('FaceMatching', 'SimilarityThreshold', fallback=0.6)
        self.top_matches = self.config.getint('FaceMatching', 'TopMatches', fallback=10)
        
        # Initialize empty face database
        self.face_db = []
        
        # Load the database
        self.load_face_db()
        
    def load_face_db(self):
        """
        Load all face data from JSON files in the database folder.
        """
        start_time = time.time()
        self.face_db = []
        
        if not os.path.exists(self.db_folder):
            self.logger.warning(f"Database folder does not exist: {self.db_folder}")
            return
            
        db_files = [f for f in os.listdir(self.db_folder) if f.endswith('.json')]
        
        if not db_files:
            self.logger.warning(f"No database files found in {self.db_folder}")
            return
            
        self.logger.info(f"Loading {len(db_files)} database files from {self.db_folder}")
        
        for db_file in db_files:
            file_path = os.path.join(self.db_folder, db_file)
            try:
                with open(file_path, 'r') as f:
                    batch_data = json.load(f)
                    self.face_db.extend(batch_data)
                    self.logger.debug(f"Loaded {len(batch_data)} faces from {db_file}")
            except json.JSONDecodeError as e:
                self.logger.error(f"Error parsing JSON in {db_file}: {e}")
            except Exception as e:
                self.logger.error(f"Error loading {db_file}: {e}")
                
        elapsed = time.time() - start_time
        self.logger.info(f"Loaded {len(self.face_db)} faces in {elapsed:.2f} seconds")
        
    def cosine_similarity(self, v1, v2):
        """
        Calculate cosine similarity between two vectors.
        
        Args:
            v1 (list or numpy.ndarray): First vector.
            v2 (list or numpy.ndarray): Second vector.
            
        Returns:
            float: Cosine similarity value (1.0 is identical, 0.0 is completely different).
        """
        # Convert to numpy arrays if they aren't already
        v1_array = np.array(v1)
        v2_array = np.array(v2)
        
        # Calculate cosine similarity (1 - cosine distance)
        return 1 - cosine(v1_array, v2_array)
    
    def angular_distance(self, v1, v2):
        """
        Calculate angular distance between two vectors.
        
        Args:
            v1 (list or numpy.ndarray): First vector.
            v2 (list or numpy.ndarray): Second vector.
            
        Returns:
            float: Angular distance in radians.
        """
        # Normalize the vectors
        v1_normalized = np.array(v1) / np.linalg.norm(v1)
        v2_normalized = np.array(v2) / np.linalg.norm(v2)
        
        # Compute the dot product of the normalized vectors
        dot_product = np.clip(np.dot(v1_normalized, v2_normalized), -1.0, 1.0)
        
        # Compute the angle between the vectors using the arccosine of the dot product
        angle = np.arccos(dot_product)
        
        return angle
    
    def pose_difference(self, pose1, pose2):
        """
        Calculate the difference between two face poses.
        
        Args:
            pose1 (list): First pose vector.
            pose2 (list): Second pose vector.
            
        Returns:
            float: Pose difference value.
        """
        # Convert to numpy arrays
        p1 = np.array(pose1)
        p2 = np.array(pose2)
        
        # Calculate Euclidean distance between pose vectors
        return np.linalg.norm(p1 - p2)
    
    def is_forward_facing(self, pose, threshold=None):
        """
        Determine if a face is forward-facing based on its pose.
        
        Args:
            pose (list): Pose vector.
            threshold (float, optional): Threshold angle in degrees.
            
        Returns:
            bool: True if the face is forward-facing, False otherwise.
        """
        if threshold is None:
            threshold = self.config.getfloat('FaceMatching', 'ForwardFacingThreshold', fallback=20)
            
        # Poses are typically represented as a vector of [yaw, pitch, roll]
        # Yaw is the left-right rotation, which is most important for determining forward-facing
        yaw = abs(pose[0])  # Take absolute value of yaw
        
        # Convert threshold from degrees to whatever units the pose uses if necessary
        # Assuming pose values are in degrees already
        return yaw < threshold
    
    def filter_by_pose(self, face_embedding, target_pose, max_pose_diff=None):
        """
        Match a face embedding against the database, filtering by pose.
        
        Args:
            face_embedding (list): Target face embedding.
            target_pose (list): Target face pose.
            max_pose_diff (float, optional): Maximum allowed pose difference.
            
        Returns:
            list: Sorted list of tuples (similarity, face_data).
        """
        if max_pose_diff is None:
            max_pose_diff = self.config.getfloat('FaceMatching', 'MaxPoseDifference', fallback=30.0)
            
        matches = []
        
        for face_data in self.face_db:
            # Skip faces without pose data
            if 'pose' not in face_data:
                continue
                
            # Calculate pose difference
            pose_diff = self.pose_difference(target_pose, face_data['pose'])
            
            # Skip faces with too different pose
            if pose_diff > max_pose_diff:
                continue
                
            # Calculate similarity
            similarity = self.cosine_similarity(face_embedding, face_data['face_embedding'])
            matches.append((similarity, face_data))
            
        # Sort by similarity (descending)
        matches.sort(key=lambda x: x[0], reverse=True)
        
        # Return top matches
        return matches[:self.top_matches]
    
    def filter_forward_facing(self, face_embedding, threshold=None):
        """
        Match a face embedding against the database, filtering for forward-facing faces.
        
        Args:
            face_embedding (list): Target face embedding.
            threshold (float, optional): Threshold angle for forward-facing.
            
        Returns:
            list: Sorted list of tuples (similarity, face_data).
        """
        matches = []
        
        for face_data in self.face_db:
            # Skip faces without pose data
            if 'pose' not in face_data:
                continue
                
            # Skip faces that are not forward-facing
            if not self.is_forward_facing(face_data['pose'], threshold):
                continue
                
            # Calculate similarity
            similarity = self.cosine_similarity(face_embedding, face_data['face_embedding'])
            matches.append((similarity, face_data))
            
        # Sort by similarity (descending)
        matches.sort(key=lambda x: x[0], reverse=True)
        
        # Return top matches
        return matches[:self.top_matches]
    
    def match_face(self, face_embedding, target_pose=None, forward_facing_threshold=None):
        """
        Match a face embedding against the database.
        
        Args:
            face_embedding (list): Target face embedding.
            target_pose (list, optional): Target face pose for pose filtering.
            forward_facing_threshold (float, optional): Threshold for forward-facing filtering.
            
        Returns:
            list: Sorted list of tuples (similarity, face_data).
        """
        # If pose filtering is requested
        if target_pose is not None:
            return self.filter_by_pose(face_embedding, target_pose)
            
        # If forward-facing filtering is requested
        if forward_facing_threshold is not None:
            return self.filter_forward_facing(face_embedding, forward_facing_threshold)
            
        # Regular matching (no filtering)
        matches = []
        
        for face_data in self.face_db:
            # Skip faces without embedding data
            if 'face_embedding' not in face_data:
                continue
                
            # Calculate similarity
            similarity = self.cosine_similarity(face_embedding, face_data['face_embedding'])
            matches.append((similarity, face_data))
            
        # Sort by similarity (descending)
        matches.sort(key=lambda x: x[0], reverse=True)
        
        # Return top matches
        return matches[:self.top_matches]