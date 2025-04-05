import tkinter as tk
import os
import sys
from utils.logger import setup_logger
from utils.config import Config
from gui.model import FaceMatcherModel
from gui.view import FaceMatcherView
from gui.controller import FaceMatcherController
import logging

def main():
    """
    Main entry point for the Face Matcher application.
    Initializes the MVC components and starts the application.
    """
    # Set up logging
    logger = setup_logger('main')
    logger.info("Starting Face Matcher Application")
    
    # Load configuration
    try:
        config = Config()
        logger.info("Configuration loaded successfully")
    except Exception as e:
        logger.error(f"Error loading configuration: {e}")
        sys.exit(1)
    
    # Ensure required directories exist
    for path_key in ['DatabaseFolder', 'ImageFolder', 'CroppedFaceFolder']:
        path = config.get('Paths', path_key)
        os.makedirs(path, exist_ok=True)
        logger.info(f"Ensured directory exists: {path}")
    
    # Initialize Tkinter
    root = tk.Tk()
    
    # Create MVC components
    try:
        # Create model
        logger.info("Initializing model...")
        model = FaceMatcherModel()
        
        # Create view
        logger.info("Initializing view...")
        view = FaceMatcherView(root)
        
        # Create controller
        logger.info("Initializing controller...")
        controller = FaceMatcherController(model, view)
        
        logger.info("MVC components initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing MVC components: {e}")
        sys.exit(1)
    
    # Start the application
    logger.info("Starting application main loop")
    view.run()

if __name__ == "__main__":
    main()
