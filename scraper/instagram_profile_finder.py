import asyncio
import aiohttp
import re
import random
import time
import os
import json
from bs4 import BeautifulSoup
from utils.logger import get_logger

class InstagramProfileFinder:
    """Specialized crawler to find public Instagram profiles for scraping."""
    
    def __init__(self, output_file="data/instagram_profiles.json"):
        self.logger = get_logger(__name__)
        self.output_file = output_file
        
        # User agent rotation for avoiding blocks
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.1 Safari/605.1.15',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36',
            'Mozilla/5.0 (iPhone; CPU iPhone OS 16_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.1 Mobile/15E148 Safari/604.1'
        ]
        
        # Known public photography/portrait/model Instagram profiles to start with
        self.seed_profiles = [
            'portraits', 'portraitphotomag', 'portrait_vision', 'portrait_shots',
            'portraitpage', 'portraitsfromtheworld', 'portraitmood', 'portraiture',
            'portraitstream', 'portraitgames', 'portraitsociety', 'portraitphotographer',
            'makeportraits', 'discoverportrait', 'portraitphotography', 'bestportraits',
            'portraitcentral', 'excellent_portraits', 'portraitstream', 'moodyportrait',
            'majestic_people', 'people_infinity', 'loves_people', 'pursuitofportraits',
            'portraitsvisuals', 'face_hunter', 'portraitfolk', 'artofvisuals'
        ]
        
        # Third-party websites that list Instagram photographers
        self.photographer_sites = [
            "https://www.format.com/magazine/resources/photography/best-instagram-photographers",
            "https://www.pixpa.com/blog/famous-portrait-photographers",
            "https://petapixel.com/2016/03/16/21-portrait-photographers-follow-instagram/",
            "https://shotkit.com/portrait-photographers/",
            "https://expertphotography.com/portrait-photographers-to-inspire-you/"
        ]
        
        # Instagram profile pattern
        self.profile_pattern = re.compile(r'(?:@|(?:(?:instagram\.com|www\.instagram\.com)/))([A-Za-z0-9._]+)(?:/)?')
        
        # Store discovered profiles
        self.profiles = set()
        
        # Load previously discovered profiles
        self._load_profiles()
    
    def _load_profiles(self):
        """Load previously discovered profiles."""
        if os.path.exists(self.output_file):
            try:
                with open(self.output_file, 'r') as f:
                    data = json.load(f)
                    if 'profiles' in data:
                        self.profiles = set(data['profiles'])
                        self.logger.info(f"Loaded {len(self.profiles)} profiles from {self.output_file}")
            except Exception as e:
                self.logger.error(f"Error loading profiles: {e}")
    
    def _save_profiles(self):
        """Save discovered profiles to file."""
        try:
            directory = os.path.dirname(self.output_file)
            if directory and not os.path.exists(directory):
                os.makedirs(directory)
                
            with open(self.output_file, 'w') as f:
                json.dump({
                    'profiles': list(self.profiles),
                    'last_updated': time.strftime("%Y-%m-%d %H:%M:%S"),
                    'count': len(self.profiles)
                }, f, indent=2)
                
            self.logger.info(f"Saved {len(self.profiles)} profiles to {self.output_file}")
        except Exception as e:
            self.logger.error(f"Error saving profiles: {e}")
    
    def _get_random_headers(self):
        """Get random headers to avoid detection."""
        user_agent = random.choice(self.user_agents)
        return {
            'User-Agent': user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://www.google.com/',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0'
        }
    
    async def fetch_url(self, session, url):
        """Fetch a URL with error handling and retry logic."""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                headers = self._get_random_headers()
                async with session.get(url, headers=headers, timeout=30) as response:
                    if response.status == 200:
                        return await response.text()
                    elif response.status == 429:  # Too Many Requests
                        self.logger.warning(f"Rate limited on {url}. Waiting before retry.")
                        await asyncio.sleep(60 + random.randint(30, 120))  # Longer wait for rate limits
                    else:
                        self.logger.warning(f"Failed to fetch {url}: HTTP {response.status}")
                        await asyncio.sleep(5 + attempt * 5)  # Increasing backoff
            except Exception as e:
                self.logger.error(f"Error fetching {url}: {e}")
                await asyncio.sleep(5 + attempt * 5)
        return None
    
    def _extract_instagram_profiles(self, html_content):
        """Extract Instagram profile usernames from HTML content."""
        if not html_content:
            return []
            
        profiles = []
        
        # Method 1: Using regex on the entire HTML
        matches = self.profile_pattern.findall(html_content)
        for username in matches:
            # Filter out common false positives
            if username not in ['explore', 'p', 'tv', 'reel', 'stories', 'direct', 'tags']:
                profiles.append(username)
        
        # Method 2: Look for links and text patterns using BeautifulSoup
        try:
            soup = BeautifulSoup(html_content, 'lxml')
            
            # Find all links
            for a_tag in soup.find_all('a'):
                href = a_tag.get('href', '')
                text = a_tag.get_text()
                
                # Check for Instagram links
                if 'instagram.com/' in href:
                    match = self.profile_pattern.search(href)
                    if match:
                        username = match.group(1)
                        if username not in ['explore', 'p', 'tv', 'reel', 'stories', 'direct', 'tags']:
                            profiles.append(username)
                
                # Check for @username mentions in text
                if '@' in text:
                    mentions = re.findall(r'@([A-Za-z0-9._]+)', text)
                    for username in mentions:
                        if username not in ['explore', 'p', 'tv', 'reel', 'stories', 'direct', 'tags']:
                            profiles.append(username)
        except Exception as e:
            self.logger.error(f"Error parsing HTML with BeautifulSoup: {e}")
        
        # Return unique profiles
        return list(set(profiles))
    
    async def check_profile_exists(self, session, username):
        """Check if an Instagram profile exists and is public."""
        # We don't want to directly access Instagram to avoid rate limits
        # Instead, use a search engine to verify
        search_url = f"https://www.bing.com/search?q=site:instagram.com+{username}"
        
        try:
            html_content = await self.fetch_url(session, search_url)
            if not html_content:
                return False
                
            # Look for indicators that profile exists
            exists = f"instagram.com/{username}" in html_content
            not_found = "Page Not Found" in html_content or "no longer exists" in html_content
            
            return exists and not not_found
        except Exception as e:
            self.logger.error(f"Error checking profile {username}: {e}")
            return False
    
    async def find_from_photography_sites(self, limit=50):
        """Find Instagram profiles from photography websites."""
        profiles = []
        
        async with aiohttp.ClientSession() as session:
            for site_url in self.photographer_sites:
                try:
                    self.logger.info(f"Searching for profiles on {site_url}")
                    html_content = await self.fetch_url(session, site_url)
                    if not html_content:
                        continue
                        
                    # Extract Instagram profiles
                    found_profiles = self._extract_instagram_profiles(html_content)
                    self.logger.info(f"Found {len(found_profiles)} potential profiles on {site_url}")
                    
                    # Add to our collection
                    for profile in found_profiles:
                        if profile not in profiles:
                            profiles.append(profile)
                            
                    # Delay between sites
                    await asyncio.sleep(random.uniform(3, 7))
                    
                    if len(profiles) >= limit:
                        break
                except Exception as e:
                    self.logger.error(f"Error processing site {site_url}: {e}")
            
            # Now verify a sample of these profiles
            self.logger.info(f"Verifying {min(20, len(profiles))} of {len(profiles)} discovered profiles...")
            
            verified_profiles = []
            sample_size = min(20, len(profiles))
            sample = random.sample(profiles, sample_size) if len(profiles) > sample_size else profiles
            
            for username in sample:
                exists = await self.check_profile_exists(session, username)
                if exists:
                    verified_profiles.append(username)
                    self.logger.debug(f"Verified profile: {username}")
                else:
                    self.logger.debug(f"Could not verify profile: {username}")
                
                # Add delay between checks
                await asyncio.sleep(random.uniform(1, 3))
            
            self.logger.info(f"Verified {len(verified_profiles)} profiles from photography sites")
            return verified_profiles
    
    async def find_related_profiles(self, seed_profiles, max_profiles=50):
        """Find related profiles by using seed profiles as a starting point."""
        if not seed_profiles:
            return []
            
        related_profiles = []
        checked_profiles = set()
        
        async with aiohttp.ClientSession() as session:
            for username in seed_profiles:
                if len(related_profiles) >= max_profiles:
                    break
                    
                if username in checked_profiles:
                    continue
                    
                checked_profiles.add(username)
                self.logger.info(f"Looking for profiles related to @{username}")
                
                # Try different approaches to find related profiles
                # 1. Search for the username and look for other profiles
                search_url = f"https://www.bing.com/search?q=instagram+photographers+similar+to+{username}"
                
                try:
                    html_content = await self.fetch_url(session, search_url)
                    if html_content:
                        profiles = self._extract_instagram_profiles(html_content)
                        
                        # Filter out already checked profiles
                        new_profiles = [p for p in profiles if p not in checked_profiles and p not in related_profiles]
                        
                        self.logger.info(f"Found {len(new_profiles)} profiles related to @{username}")
                        
                        # Add the new profiles
                        for profile in new_profiles:
                            if profile not in related_profiles:
                                related_profiles.append(profile)
                                
                        # Don't exceed our limit
                        if len(related_profiles) >= max_profiles:
                            break
                except Exception as e:
                    self.logger.error(f"Error finding related profiles for @{username}: {e}")
                
                # Add delay between requests
                await asyncio.sleep(random.uniform(2, 5))
            
            # Now verify some of these profiles
            if related_profiles:
                self.logger.info(f"Verifying {min(10, len(related_profiles))} of {len(related_profiles)} related profiles...")
                
                verified_profiles = []
                sample_size = min(10, len(related_profiles))
                sample = random.sample(related_profiles, sample_size) if len(related_profiles) > sample_size else related_profiles
                
                for username in sample:
                    exists = await self.check_profile_exists(session, username)
                    if exists:
                        verified_profiles.append(username)
                
                # Estimate total number of valid profiles
                if sample_size < len(related_profiles):
                    valid_ratio = len(verified_profiles) / sample_size
                    estimated_valid = int(len(related_profiles) * valid_ratio)
                    self.logger.info(f"Estimated {estimated_valid} valid profiles from related profile search")
                    
                    # If verification ratio is poor, just use verified ones
                    if valid_ratio < 0.5:
                        return verified_profiles
                    
                    # Otherwise return all, since most are probably valid
                    return related_profiles[:max_profiles]
                else:
                    return verified_profiles
        
        return related_profiles[:max_profiles]
    
    async def run(self, target_count=200, max_runtime_minutes=30):
        """Run the Instagram profile finder."""
        self.logger.info(f"Starting Instagram profile finder. Target: {target_count} profiles")
        
        # Set end time
        start_time = time.time()
        end_time = start_time + (max_runtime_minutes * 60)
        
        # First, use our seed profiles directly
        self.logger.info(f"Starting with {len(self.seed_profiles)} seed profiles")
        self.profiles.update(self.seed_profiles)
        
        # Save initial progress
        if self.profiles:
            self._save_profiles()
        
        # 1. Find profiles from photography websites
        if time.time() < end_time and len(self.profiles) < target_count:
            photography_profiles = await self.find_from_photography_sites(limit=100)
            self.profiles.update(photography_profiles)
            self.logger.info(f"Found {len(photography_profiles)} profiles from photography sites. " 
                            f"Total unique profiles: {len(self.profiles)}")
            
            # Save progress
            self._save_profiles()
        
        # 2. Find related profiles using seeds
        if time.time() < end_time and len(self.profiles) < target_count:
            # Use some of our existing profiles as seeds for finding related ones
            seed_samples = list(self.profiles)[:10]  # Use up to 10 seeds
            
            related_profiles = await self.find_related_profiles(
                seed_samples,
                max_profiles=target_count - len(self.profiles)
            )
            
            self.profiles.update(related_profiles)
            self.logger.info(f"Found {len(related_profiles)} related profiles. " 
                            f"Total unique profiles: {len(self.profiles)}")
            
            # Save progress
            self._save_profiles()
        
        # Final save
        self._save_profiles()
        
        elapsed = time.time() - start_time
        self.logger.info(f"Instagram profile finder completed in {elapsed:.2f}s. "
                        f"Found {len(self.profiles)} unique profiles.")
        
        return list(self.profiles)

# Function to run from command line
async def find_instagram_profiles(target_count=200, max_runtime_minutes=30, output_file="data/instagram_profiles.json"):
    finder = InstagramProfileFinder(output_file=output_file)
    profiles = await finder.run(target_count=target_count, max_runtime_minutes=max_runtime_minutes)
    return profiles

# Command line entry point
def main():
    import argparse
    parser = argparse.ArgumentParser(description='Find public Instagram profiles')
    parser.add_argument('--count', type=int, default=200, help='Target number of profiles to find')
    parser.add_argument('--time', type=int, default=30, help='Maximum runtime in minutes')
    parser.add_argument('--output', type=str, default="data/instagram_profiles.json", help='Output file path')
    
    args = parser.parse_args()
    
    asyncio.run(find_instagram_profiles(
        target_count=args.count,
        max_runtime_minutes=args.time,
        output_file=args.output
    ))

if __name__ == "__main__":
    main()