import configparser
import os
import logging

class Config:
    """
    Configuration manager for the application.
    Loads settings from config.ini and provides access to configuration values.
    """
    _instance = None
    
    def __new__(cls):
        """Singleton pattern to ensure only one config instance exists."""
        if cls._instance is None:
            cls._instance = super(Config, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize the configuration if not already initialized."""
        if self._initialized:
            return
            
        self.logger = logging.getLogger(__name__)
        self.config = configparser.ConfigParser()
        
        # Find config file
        config_paths = [
            'config.ini',  # Current directory
            os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.ini'),  # Project root
        ]
        
        config_loaded = False
        for config_path in config_paths:
            if os.path.exists(config_path):
                try:
                    self.config.read(config_path)
                    self.logger.info(f"Loaded configuration from {config_path}")
                    config_loaded = True
                    break
                except Exception as e:
                    self.logger.error(f"Error loading config from {config_path}: {e}")
        
        if not config_loaded:
            self.logger.warning("No configuration file found, using defaults")
            self._set_defaults()
            
        # Ensure directories exist
        self._ensure_directories()
        self._initialized = True
    
    def _set_defaults(self):
        """Set default configuration values if no config file is found."""
        self.config['Paths'] = {
            'DatabaseFolder': 'data/database',
            'ImageFolder': 'data/images',
            'CroppedFaceFolder': 'data/cropped_faces'
        }
        
        self.config['FaceDetection'] = {
            'DetectionThreshold': '0.8',
            'DetectionSize': '640',
            'UseGPU': 'True',
            'GPUId': '0'
        }
        
        self.config['FaceMatching'] = {
            'SimilarityThreshold': '0.6',
            'TopMatches': '10',
            'ForwardFacingThreshold': '20'
        }
        
        self.config['GUI'] = {
            'CanvasWidth': '500',
            'CanvasHeight': '500'
        }
    
    def _ensure_directories(self):
        """Ensure that all required directories exist."""
        for key in ['DatabaseFolder', 'ImageFolder', 'CroppedFaceFolder']:
            if 'Paths' in self.config and key in self.config['Paths']:
                directory = self.config['Paths'][key]
                os.makedirs(directory, exist_ok=True)
                self.logger.info(f"Ensured directory exists: {directory}")
    
    def get(self, section, key, fallback=None):
        """Get a configuration value."""
        return self.config.get(section, key, fallback=fallback)
    
    def getint(self, section, key, fallback=None):
        """Get an integer configuration value."""
        return self.config.getint(section, key, fallback=fallback)
    
    def getfloat(self, section, key, fallback=None):
        """Get a float configuration value."""
        return self.config.getfloat(section, key, fallback=fallback)
    
    def getboolean(self, section, key, fallback=None):
        """Get a boolean configuration value."""
        return self.config.getboolean(section, key, fallback=fallback)
    
    def get_detection_size(self):
        """Get the detection size as a tuple."""
        size = self.getint('FaceDetection', 'DetectionSize', fallback=640)
        return (size, size)
    
    def get_gpu_id(self):
        """Get the GPU ID, or -1 if GPU is disabled."""
        if self.getboolean('FaceDetection', 'UseGPU', fallback=True):
            return self.getint('FaceDetection', 'GPUId', fallback=0)
        return -1  # Use CPU
