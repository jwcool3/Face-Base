from tkinter import filedialog, messagebox
from utils.logger import get_logger
from PIL import Image, ImageTk
import cv2
import numpy as np
import os
from gui.scraper_dialog import ScraperDialog
from scraper.main import scrape_and_download

class FaceMatcherController:
    """
    Controller component of the MVC architecture for the Face Matcher application.
    Handles user input and updates the model and view accordingly.
    """
    
    def __init__(self, model, view):
        """
        Initialize the controller with the model and view.
        
        Args:
            model: The FaceMatcherModel instance.
            view: The FaceMatcherView instance.
        """
        self.logger = get_logger(__name__)
        self.model = model
        self.view = view
        
        # Register callbacks for view events
        self._register_callbacks()
        
        # Update the database size label
        self.update_database_info()
    
    def _register_callbacks(self):
        """Register callbacks for view events."""
        # Button callbacks
        self.view.set_upload_callback(self.upload_images)
        self.view.set_match_callback(self.match_face)
        self.view.set_pose_filter_callback(self.toggle_pose_filter)
        self.view.set_forward_facing_filter_callback(self.toggle_forward_facing_filter)
        self.view.set_landmarks_overlay_callback(self.toggle_landmarks_overlay)
        self.view.set_age_gender_overlay_callback(self.toggle_age_gender_overlay)
        self.view.set_back_callback(self.display_previous_image)
        self.view.set_forward_callback(self.display_next_image)
        self.view.set_scraper_callback(self.show_scraper_dialog)
    
    def update_database_info(self):
        """Update the database size label in the view."""
        db_size = self.model.get_database_size()
        self.view.update_total_faces_label(db_size)
    
    def upload_images(self):
        """
        Handle uploading and processing images.
        Open a file dialog for the user to select images, then process them.
        """
        # Open a file dialog for the user to select images
        file_paths = filedialog.askopenfilenames()
        
        if not file_paths:
            return  # User cancelled
            
        for file_path in file_paths:
            # Process the image
            success = self.model.process_image(file_path)
            
            if success:
                # Display the processed image
                self.display_uploaded_image(file_path)
                # Match the face
                self.match_face()
                break  # Process only the first successful image for now
            else:
                messagebox.showwarning("Warning", f"No faces detected in {os.path.basename(file_path)}")
    
    def display_uploaded_image(self, image_path):
        """
        Display the uploaded image in the view.
        
        Args:
            image_path (str): Path to the image file.
        """
        try:
            # Open the original image
            original_image = Image.open(image_path)
            
            # Make a copy for face processing
            image = original_image.copy()
            
            # Apply overlays if enabled
            if self.model.landmarks_overlay_enabled and self.model.landmarks_2d:
                image = self.overlay_landmarks(image, self.model.landmarks_2d)
                
            if self.model.age_gender_overlay_enabled:
                image = self.overlay_age_gender(
                    image, 
                    self.model.current_face_age,
                    self.model.current_face_gender
                )
            
            # Display images in the view
            self.view.display_uploaded_image(image)
            self.view.display_full_uploaded_image(original_image)
            
        except Exception as e:
            self.logger.error(f"Error displaying uploaded image {image_path}: {e}")
            messagebox.showerror("Error", f"Error displaying image: {e}")
    
    def match_face(self):
        """Match the current face against the database and display results."""
        success = self.model.match_face()
        
        if not success:
            messagebox.showinfo("Info", "No matching faces found in the database.")
            return
            
        # Display the match results
        self.display_match_results()
        
        # Update the navigation buttons
        self.update_navigation_buttons()
    
    def display_match_results(self):
        """Display the current match result in the view."""
        match = self.model.get_current_match()
        
        if not match:
            return
            
        similarity, face_data = match
        
        # Get the image paths
        matched_face_path = face_data.get('img_path')
        source_image_path = face_data.get('image_source')
        
        if not matched_face_path or not os.path.exists(matched_face_path):
            self.logger.warning(f"Matched face image path does not exist: {matched_face_path}")
            return
            
        try:
            # Load the matched face image
            matched_face = Image.open(matched_face_path)
            
            # Apply overlays if enabled
            if self.model.landmarks_overlay_enabled and 'landmark_2d_106' in face_data:
                matched_face = self.overlay_landmarks(matched_face, face_data['landmark_2d_106'])
                
            if self.model.age_gender_overlay_enabled:
                matched_face = self.overlay_age_gender(
                    matched_face, 
                    face_data.get('age'),
                    face_data.get('gender')
                )
            
            # Display the matched face
            self.view.display_matched_image(matched_face)
            
            # Try to display the source image if it exists
            if source_image_path and os.path.exists(source_image_path):
                source_image = Image.open(source_image_path)
                
                # Apply overlays to source image if needed
                if self.model.age_gender_overlay_enabled:
                    source_image = self.overlay_age_gender(
                        source_image,
                        face_data.get('age'),
                        face_data.get('gender')
                    )
                    
                self.view.display_full_matched_image(source_image)
            
            # Update the match info text
            self.view.update_match_info(
                similarity=similarity,
                source=source_image_path,
                resolution=face_data.get('resolution', 'Unknown'),
                age=face_data.get('age', 'Unknown'),
                gender=face_data.get('gender', 'Unknown')
            )
            
        except Exception as e:
            self.logger.error(f"Error displaying match results: {e}")
            messagebox.showerror("Error", f"Error displaying match results: {e}")
    
    def display_previous_image(self):
        """Display the previous match result."""
        match = self.model.previous_match()
        
        if match:
            self.display_match_results()
            self.update_navigation_buttons()
    
    def display_next_image(self):
        """Display the next match result."""
        match = self.model.next_match()
        
        if match:
            self.display_match_results()
            self.update_navigation_buttons()
    
    def update_navigation_buttons(self):
        """Update the state of navigation buttons based on available matches."""
        self.view.update_navigation_buttons(
            has_previous=self.model.has_previous_match(),
            has_next=self.model.has_next_match()
        )
    
    def toggle_pose_filter(self):
        """Toggle the pose filter and update UI."""
        enabled = self.model.toggle_pose_filter()
        self.view.update_pose_filter_button(enabled)
        
        # Re-match with the new filter settings
        self.match_face()
    
    def toggle_forward_facing_filter(self):
        """Toggle the forward-facing filter and update UI."""
        enabled = self.model.toggle_forward_facing_filter()
        self.view.update_forward_facing_filter_button(enabled)
        
        # Re-match with the new filter settings
        self.match_face()
    
    def toggle_landmarks_overlay(self):
        """Toggle the landmarks overlay and update UI."""
        enabled = self.model.toggle_landmarks_overlay()
        self.view.update_landmarks_overlay_button(enabled)
        
        # Redisplay the current images with updated overlay
        self.display_uploaded_image(self.model.current_image_path)
        self.display_match_results()
    
    def toggle_age_gender_overlay(self):
        """Toggle the age and gender overlay and update UI."""
        enabled = self.model.toggle_age_gender_overlay()
        self.view.update_age_gender_overlay_button(enabled)
        
        # Redisplay the current images with updated overlay
        self.display_uploaded_image(self.model.current_image_path)
        self.display_match_results()
        
    def show_scraper_dialog(self):
        """Show the web scraper dialog."""
        self.logger.info("Opening web scraper dialog")
        ScraperDialog(self.view.root, scrape_and_download)
    
    @staticmethod
    def overlay_landmarks(image, landmarks):
        """
        Overlay facial landmarks on an image.
        
        Args:
            image (PIL.Image): The image to overlay landmarks on.
            landmarks (list): List of (x, y) landmark coordinates.
            
        Returns:
            PIL.Image: The image with landmarks overlaid.
        """
        # Convert PIL image to numpy array for OpenCV
        image_np = np.array(image)
        
        # Ensure image is in RGB format (OpenCV uses BGR)
        if len(image_np.shape) == 2:  # Grayscale
            image_np = cv2.cvtColor(image_np, cv2.COLOR_GRAY2RGB)
        elif image_np.shape[2] == 4:  # RGBA
            image_np = cv2.cvtColor(image_np, cv2.COLOR_RGBA2RGB)
        elif image_np.shape[2] == 3:  # BGR (OpenCV default)
            image_np = cv2.cvtColor(image_np, cv2.COLOR_BGR2RGB)
        
        # Draw the landmarks on the image
        for x, y in landmarks:
            cv2.circle(image_np, (int(x), int(y)), 2, (0, 255, 0), -1)
        
        # Convert back to PIL image
        return Image.fromarray(image_np)
    
    @staticmethod
    def overlay_age_gender(image, age, gender):
        """
        Overlay age and gender information on an image.
        
        Args:
            image (PIL.Image): The image to overlay information on.
            age (float): Age estimate.
            gender (str): Gender estimate.
            
        Returns:
            PIL.Image: The image with information overlaid.
        """
        # Convert PIL image to numpy array for OpenCV
        image_np = np.array(image)
        
        # Ensure image is in RGB format (OpenCV uses BGR)
        if len(image_np.shape) == 2:  # Grayscale
            image_np = cv2.cvtColor(image_np, cv2.COLOR_GRAY2RGB)
        elif image_np.shape[2] == 4:  # RGBA
            image_np = cv2.cvtColor(image_np, cv2.COLOR_RGBA2RGB)
        elif image_np.shape[2] == 3:  # BGR (OpenCV default)
            image_np = cv2.cvtColor(image_np, cv2.COLOR_BGR2RGB)
        
        # Format the text
        if age is not None and gender is not None:
            text = f"{gender}, {int(age) if isinstance(age, (int, float)) else age}"
            
            # Draw text background for better visibility
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.7
            font_thickness = 2
            text_size = cv2.getTextSize(text, font, font_scale, font_thickness)[0]
            
            # Draw a semi-transparent background for the text
            overlay = image_np.copy()
            cv2.rectangle(
                overlay, 
                (10, 10), 
                (10 + text_size[0] + 10, 10 + text_size[1] + 10),
                (0, 0, 0),
                -1
            )
            alpha = 0.6  # Transparency factor
            cv2.addWeighted(overlay, alpha, image_np, 1 - alpha, 0, image_np)
            
            # Put the text on the image
            cv2.putText(
                image_np,
                text,
                (15, 15 + text_size[1]),
                font,
                font_scale,
                (255, 255, 255),  # White text
                font_thickness
            )
        
        # Convert back to PIL image
        return Image.fromarray(image_np)