import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
from utils.logger import get_logger
import os

class FaceMatcherView:
    """
    View component of the MVC architecture for the Face Matcher application.
    Handles UI rendering and user interaction.
    """
    
    def __init__(self, root):
        """
        Initialize the view with the root Tk window.
        
        Args:
            root (tk.Tk): The root window of the application.
        """
        self.logger = get_logger(__name__)
        self.root = root
        self.root.title("Face Matcher Application")
        
        # Set minimum window size
        self.root.minsize(1200, 800)
        
        # Create frames for layout
        self._create_frames()
        
        # Create UI elements
        self._create_controls()
        self._create_display_areas()
        
        # Initialize callback placeholders
        self.upload_callback = None
        self.match_callback = None
        self.pose_filter_callback = None
        self.forward_facing_filter_callback = None
        self.landmarks_overlay_callback = None
        self.age_gender_overlay_callback = None
        self.back_callback = None
        self.forward_callback = None
        
    # Callback setters
    def set_upload_callback(self, callback):
        """Set the callback for the upload button."""
        self.upload_callback = callback
        self.upload_button.config(command=callback)
    
    def set_match_callback(self, callback):
        """Set the callback for the match button."""
        self.match_callback = callback
        self.match_button.config(command=callback)
    
    def set_pose_filter_callback(self, callback):
        """Set the callback for the pose filter button."""
        self.pose_filter_callback = callback
        self.pose_filter_button.config(command=callback)
    
    def set_forward_facing_filter_callback(self, callback):
        """Set the callback for the forward-facing filter button."""
        self.forward_facing_filter_callback = callback
        self.forward_facing_filter_button.config(command=callback)
    
    def set_landmarks_overlay_callback(self, callback):
        """Set the callback for the landmarks overlay button."""
        self.landmarks_overlay_callback = callback
        self.landmarks_overlay_button.config(command=callback)
    
    def set_age_gender_overlay_callback(self, callback):
        """Set the callback for the age and gender overlay button."""
        self.age_gender_overlay_callback = callback
        self.age_gender_overlay_button.config(command=callback)
    
    def set_back_callback(self, callback):
        """Set the callback for the back button."""
        self.back_callback = callback
        self.back_button.config(command=callback)
    
    def set_forward_callback(self, callback):
        """Set the callback for the forward button."""
        self.forward_callback = callback
        self.forward_button.config(command=callback)
        
    # UI update methods
    def update_total_faces_label(self, count):
        """Update the total faces label with the current count."""
        self.total_faces_label.config(text=f"Total faces in database: {count}")
    
    def update_pose_filter_button(self, enabled):
        """Update the pose filter button text based on its state."""
        if enabled:
            self.pose_filter_button.config(text="Disable Pose Filter")
        else:
            self.pose_filter_button.config(text="Filter by Pose")
    
    def update_forward_facing_filter_button(self, enabled):
        """Update the forward-facing filter button text based on its state."""
        if enabled:
            self.forward_facing_filter_button.config(text="Disable Forward-Facing Filter")
        else:
            self.forward_facing_filter_button.config(text="Filter Forward-Facing")
    
    def update_landmarks_overlay_button(self, enabled):
        """Update the landmarks overlay button text based on its state."""
        if enabled:
            self.landmarks_overlay_button.config(text="Disable Landmarks")
        else:
            self.landmarks_overlay_button.config(text="Overlay Landmarks")
    
    def update_age_gender_overlay_button(self, enabled):
        """Update the age and gender overlay button text based on its state."""
        if enabled:
            self.age_gender_overlay_button.config(text="Disable Age/Gender")
        else:
            self.age_gender_overlay_button.config(text="Overlay Age/Gender")
    
    def update_navigation_buttons(self, has_previous, has_next):
        """Update the state of navigation buttons based on availability of matches."""
        self.back_button.config(state='normal' if has_previous else 'disabled')
        self.forward_button.config(state='normal' if has_next else 'disabled')
    
    def update_match_info(self, similarity, source, resolution, age, gender):
        """Update the match information text widget."""
        # Clear the text widget
        self.match_info_text.delete('1.0', 'end')
        
        # Add the match information
        self.match_info_text.insert('end', f"Match Score: {similarity:.4f}\n\n")
        self.match_info_text.insert('end', f"Source Image: {os.path.basename(source)}\n\n")
        self.match_info_text.insert('end', f"Resolution: {resolution}\n\n")
        self.match_info_text.insert('end', f"Age: {age}\n\n")
        self.match_info_text.insert('end', f"Gender: {gender}\n\n")
        
        # Disable editing
        self.match_info_text.config(state='disabled')
        
    # Image display methods
    def display_uploaded_image(self, image):
        """Display the uploaded image on the canvas."""
        # Resize the image to fit the canvas
        resized_image = self._resize_image(image, 400, 400)
        
        # Convert to PhotoImage
        self.photo_uploaded = ImageTk.PhotoImage(resized_image)
        
        # Clear the canvas and display the image
        self.canvas_uploaded.delete("all")
        self.canvas_uploaded.create_image(0, 0, anchor='nw', image=self.photo_uploaded)
    
    def display_full_uploaded_image(self, image):
        """Display the full uploaded image on the canvas."""
        # Resize the image to fit the canvas
        resized_image = self._resize_image(image, 400, 400)
        
        # Convert to PhotoImage
        self.photo_full_uploaded = ImageTk.PhotoImage(resized_image)
        
        # Clear the canvas and display the image
        self.canvas_full_uploaded.delete("all")
        self.canvas_full_uploaded.create_image(0, 0, anchor='nw', image=self.photo_full_uploaded)
    
    def display_matched_image(self, image):
        """Display the matched image on the canvas."""
        # Resize the image to fit the canvas
        resized_image = self._resize_image(image, 400, 400)
        
        # Convert to PhotoImage
        self.photo_matched = ImageTk.PhotoImage(resized_image)
        
        # Clear the canvas and display the image
        self.canvas_matched.delete("all")
        self.canvas_matched.create_image(0, 0, anchor='nw', image=self.photo_matched)
    
    def display_full_matched_image(self, image):
        """Display the full matched image on the canvas."""
        # Resize the image to fit the canvas
        resized_image = self._resize_image(image, 400, 400)
        
        # Convert to PhotoImage
        self.photo_full_matched = ImageTk.PhotoImage(resized_image)
        
        # Clear the canvas and display the image
        self.canvas_full_matched.delete("all")
        self.canvas_full_matched.create_image(0, 0, anchor='nw', image=self.photo_full_matched)
    
    @staticmethod
    def _resize_image(image, width, height):
        """
        Resize an image to fit within the specified dimensions while maintaining aspect ratio.
        
        Args:
            image (PIL.Image): The image to resize.
            width (int): Target width.
            height (int): Target height.
            
        Returns:
            PIL.Image: Resized image.
        """
        # Get the original dimensions
        original_width, original_height = image.size
        
        # Calculate the scaling factor
        width_ratio = width / original_width
        height_ratio = height / original_height
        scale_factor = min(width_ratio, height_ratio)
        
        # Calculate the new dimensions
        new_width = int(original_width * scale_factor)
        new_height = int(original_height * scale_factor)
        
        # Resize the image
        return image.resize((new_width, new_height), Image.LANCZOS)
    
    def run(self):
        """Start the main application loop."""
        self.root.mainloop()
        
        # Initialize photo image references
        self.photo_uploaded = None
        self.photo_full_uploaded = None
        self.photo_matched = None
        self.photo_full_matched = None
    
    def _create_frames(self):
        """Create the main frames for the application layout."""
        # Top frame for controls
        self.top_frame = ttk.Frame(self.root, padding=10)
        self.top_frame.pack(side='top', fill='x')
        
        # Bottom frame for display areas
        self.bottom_frame = ttk.Frame(self.root, padding=10)
        self.bottom_frame.pack(side='bottom', fill='both', expand=True)
        
        # Left frame for uploaded images
        self.left_frame = ttk.LabelFrame(self.bottom_frame, text="Uploaded Image", padding=5)
        self.left_frame.pack(side='left', fill='both', expand=True)
        
        # Center frame for match info
        self.center_frame = ttk.LabelFrame(self.bottom_frame, text="Match Information", padding=5)
        self.center_frame.pack(side='left', fill='both', expand=True)
        
        # Right frame for matched images
        self.right_frame = ttk.LabelFrame(self.bottom_frame, text="Matched Image", padding=5)
        self.right_frame.pack(side='left', fill='both', expand=True)
    
    def _create_controls(self):
        """Create the control buttons and elements in the top frame."""
        # Left side controls
        left_controls = ttk.Frame(self.top_frame)
        left_controls.pack(side='left', fill='x', expand=True)
        
        # Upload button
        self.upload_button = ttk.Button(left_controls, text="Upload Image")
        self.upload_button.pack(side='left', padx=5)
        
        # Match button
        self.match_button = ttk.Button(left_controls, text="Match Face")
        self.match_button.pack(side='left', padx=5)
        
        # Pose filter button
        self.pose_filter_button = ttk.Button(left_controls, text="Filter by Pose")
        self.pose_filter_button.pack(side='left', padx=5)
        
        # Forward-facing filter button
        self.forward_facing_filter_button = ttk.Button(left_controls, text="Filter Forward-Facing")
        self.forward_facing_filter_button.pack(side='left', padx=5)
        
        # Landmarks overlay button
        self.landmarks_overlay_button = ttk.Button(left_controls, text="Overlay Landmarks")
        self.landmarks_overlay_button.pack(side='left', padx=5)
        
        # Age and gender overlay button
        self.age_gender_overlay_button = ttk.Button(left_controls, text="Overlay Age/Gender")
        self.age_gender_overlay_button.pack(side='left', padx=5)
        
        # Right side controls
        right_controls = ttk.Frame(self.top_frame)
        right_controls.pack(side='right', fill='x')
        
        # Navigation buttons
        self.back_button = ttk.Button(right_controls, text="Previous")
        self.back_button.pack(side='left', padx=5)
        
        self.forward_button = ttk.Button(right_controls, text="Next")
        self.forward_button.pack(side='left', padx=5)
        
        # Database info label
        self.total_faces_label = ttk.Label(right_controls, text="Total faces in database: 0")
        self.total_faces_label.pack(side='left', padx=10)
    
    def _create_display_areas(self):
        """Create the display areas for images and information."""
        # Left frame - Uploaded image displays
        self.uploaded_image_label = ttk.Label(self.left_frame, text="Face")
        self.uploaded_image_label.pack(side='top', pady=5)
        
        self.canvas_uploaded = tk.Canvas(self.left_frame, width=400, height=400, bg='white')
        self.canvas_uploaded.pack(side='top', pady=5)
        
        self.full_uploaded_image_label = ttk.Label(self.left_frame, text="Full Image")
        self.full_uploaded_image_label.pack(side='top', pady=5)
        
        self.canvas_full_uploaded = tk.Canvas(self.left_frame, width=400, height=400, bg='white')
        self.canvas_full_uploaded.pack(side='top', pady=5)
        
        # Center frame - Match information
        self.match_info_text = tk.Text(self.center_frame, width=40, height=20, wrap=tk.WORD)
        self.match_info_text.pack(side='top', fill='both', expand=True, pady=5)
        
        # Add a scrollbar to the text widget
        scrollbar = ttk.Scrollbar(self.match_info_text, command=self.match_info_text.yview)
        scrollbar.pack(side='right', fill='y')
        self.match_info_text.config(yscrollcommand=scrollbar.set)
        
        # Right frame - Matched image displays
        self.matched_image_label = ttk.Label(self.right_frame, text="Matched Face")
        self.matched_image_label.pack(side='top', pady=5)
        
        self.canvas_matched = tk.Canvas(self.right_frame, width=400, height=400, bg='white')
        self.canvas_matched.pack(side='top', pady=5)
        
        self.full_matched_image_label = ttk.Label(self.right_frame, text="Full Matched Image")
        self.full_matched_image_label.pack(side='top', pady=5)
        
        self.canvas_full_matched = tk.Canvas(self.right_frame, width=400, height=400, bg='white')
        self.canvas_full_matched.pack(side='top', pady=5)