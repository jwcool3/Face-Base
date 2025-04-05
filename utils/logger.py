import logging
import os
from datetime import datetime

def setup_logger(name=None, log_dir='logs'):
    """
    Set up a logger for the application.
    
    Args:
        name (str, optional): Logger name. Defaults to None (root logger).
        log_dir (str, optional): Directory to store log files. Defaults to 'logs'.
    
    Returns:
        logging.Logger: Configured logger instance
    """
    # Ensure log directory exists
    os.makedirs(log_dir, exist_ok=True)
    
    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    
    # Create console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    
    # Create file handler
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = f"{timestamp}.log" if name is None else f"{timestamp}_{name}.log"
    file_handler = logging.FileHandler(os.path.join(log_dir, log_file))
    file_handler.setLevel(logging.DEBUG)
    
    # Create formatters
    console_format = logging.Formatter('%(levelname)s - %(message)s')
    file_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Set formatters
    console_handler.setFormatter(console_format)
    file_handler.setFormatter(file_format)
    
    # Add handlers to logger
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    
    return logger

def get_logger(name=None):
    """
    Get a logger instance with the given name.
    Creates a new logger if it doesn't exist.
    
    Args:
        name (str, optional): Logger name. Defaults to None (root logger).
    
    Returns:
        logging.Logger: Logger instance
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger = setup_logger(name)
    return logger
