import json
import os
from urllib.parse import urljoin, urlparse
import hashlib
from utils.logger import get_logger

logger = get_logger(__name__)

def get_absolute_url(base_url, link):
    """
    Convert a relative URL to an absolute URL.
    
    Args:
        base_url (str): The base URL.
        link (str): The link to convert.
        
    Returns:
        str: Absolute URL.
    """
    if bool(urlparse(link).netloc):
        return link
    else:
        return urljoin(base_url, link)

def save_crawler_state(state, file_path='crawler_state.json'):
    """
    Save the current state of the crawler to a JSON file.
    
    Args:
        state (dict): Dictionary containing crawler state info.
        file_path (str): Path to save the state file.
    """
    try:
        with open(file_path, 'w') as f:
            json.dump(state, f, indent=4)
        logger.info(f"Crawler state saved to {file_path}")
    except Exception as e:
        logger.error(f"Error saving crawler state: {e}")

def load_crawler_state(file_path='crawler_state.json'):
    """
    Load the crawler state from a JSON file.
    
    Args:
        file_path (str): Path to the state file.
        
    Returns:
        dict: The crawler state, or None if the file doesn't exist.
    """
    try:
        with open(file_path, 'r') as f:
            state = json.load(f)
        logger.info(f"Crawler state loaded from {file_path}")
        return state
    except FileNotFoundError:
        logger.warning(f"Crawler state file not found: {file_path}")
        return None
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing crawler state file: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error loading crawler state: {e}")
        return None

def sanitize_filename(url):
    """
    Create a sanitized filename from a URL.
    
    Args:
        url (str): The URL to sanitize.
        
    Returns:
        str: Sanitized filename (MD5 hash of the URL).
    """
    return hashlib.md5(url.encode('utf-8')).hexdigest()

def ensure_directory(directory):
    """
    Ensure a directory exists, creating it if necessary.
    
    Args:
        directory (str): Directory path to ensure exists.
    """
    try:
        os.makedirs(directory, exist_ok=True)
        logger.debug(f"Ensured directory exists: {directory}")
    except Exception as e:
        logger.error(f"Error ensuring directory exists: {e}")
        raise

def get_image_urls_from_json(json_path='crawler_state.json'):
    """
    Get image URLs from a JSON file.
    
    Args:
        json_path (str): Path to the JSON file.
        
    Returns:
        list: List of image URLs.
    """
    try:
        with open(json_path, 'r') as f:
            data = json.load(f)
        return data.get('all_image_urls', [])
    except FileNotFoundError:
        logger.warning(f"JSON file not found: {json_path}")
        return []
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing JSON file: {e}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error loading JSON file: {e}")
        return []
