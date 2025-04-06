import random
from urllib.parse import urlparse
from utils.logger import get_logger

class SocialMediaTargetSelector:
    """Selects social media and similar websites containing public photos of individuals."""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        
        # Public social media platforms and hashtag pages
        self.social_platforms = [
            # Instagram Explore Tags
            "https://www.instagram.com/explore/tags/portrait/",
            "https://www.instagram.com/explore/tags/selfie/",
            "https://www.instagram.com/explore/tags/people/",
            
            # Twitter Search URLs
            "https://twitter.com/search?q=selfie&src=typed_query&f=image",
            "https://twitter.com/search?q=portrait&src=typed_query&f=image",
            "https://twitter.com/search?q=headshot&src=typed_query&f=image",
            "https://twitter.com/search?q=people&src=typed_query&f=image",
            
            # Pinterest
            "https://www.pinterest.com/search/pins/?q=people%20portrait",
            
            # Reddit
            "https://www.reddit.com/r/portraits/",
            "https://www.reddit.com/r/selfies/",
            "https://www.reddit.com/r/humanporn/",  # SFW photography of people
            
            # Flickr
            "https://www.flickr.com/groups/portraits/pool/"
        ]
        
        # Public photo sharing sites with people tags
        self.photo_sharing_sites = [
            "https://500px.com/search?q=portrait&type=photos",
            "https://www.flickr.com/search/?text=portrait%20people&view_all=1",
            "https://www.smugmug.com/search/?q=portrait&type=images",
            "https://unsplash.com/s/photos/people",
            "https://www.pexels.com/search/people/",
            "https://pixabay.com/images/search/people/"
        ]
        
        # Public personal blogs and smaller community sites
        self.community_sites = [
            "https://medium.com/search?q=portrait",
            "https://wordpress.com/tag/portrait",
            "https://tumblr.com/tagged/portrait",
            "https://www.deviantart.com/tag/portrait"
        ]
        
        # Track used targets to avoid repeats
        self.used_targets = set()
    
    def get_next_target(self):
        """Returns the next site to scrape based on current strategy."""
        # Check if any sources are configured
        all_sources = self.social_platforms + self.photo_sharing_sites + self.community_sites
        if not all_sources:
            self.logger.warning("No sources configured, cannot select a target")
            return None
            
        # Log how many sources are available in each category
        self.logger.debug(f"Available sources: Social: {len(self.social_platforms)}, " +
                        f"Photo: {len(self.photo_sharing_sites)}, " +
                        f"Community: {len(self.community_sites)}")
            
        # 60% chance of social media, 30% photo sharing, 10% community sites - but only if they have sources
        r = random.random()
        potential_targets = []
        
        if r < 0.6 and self.social_platforms:
            potential_targets = [url for url in self.social_platforms if url not in self.used_targets]
            category = "social media"
        elif r < 0.9 and self.photo_sharing_sites:
            potential_targets = [url for url in self.photo_sharing_sites if url not in self.used_targets]
            category = "photo sharing"
        elif self.community_sites:
            potential_targets = [url for url in self.community_sites if url not in self.used_targets]
            category = "community"
        else:
            # If we got here, the random selection didn't work - try any category with sources
            if self.social_platforms:
                potential_targets = [url for url in self.social_platforms if url not in self.used_targets]
                category = "social media (fallback)"
            elif self.photo_sharing_sites:
                potential_targets = [url for url in self.photo_sharing_sites if url not in self.used_targets]
                category = "photo sharing (fallback)"
            elif self.community_sites:
                potential_targets = [url for url in self.community_sites if url not in self.used_targets]
                category = "community (fallback)"
        
        # If we've used all targets in the selected category, reset used targets for that category only
        if not potential_targets:
            self.logger.info(f"All targets in {category} category used, resetting")
            self.used_targets = set()
            
            # Try again with empty used_targets set
            if category.startswith("social"):
                potential_targets = self.social_platforms
            elif category.startswith("photo"):
                potential_targets = self.photo_sharing_sites
            elif category.startswith("community"):
                potential_targets = self.community_sites
        
        # Select and mark as used
        if potential_targets:
            target = random.choice(potential_targets)
            self.used_targets.add(target)
            self.logger.info(f"Selected target from {category}: {target}")
            return target
            
        # This should never happen if we have any sources configured
        self.logger.warning("No targets available in any configured category")
        return None
    
    def add_custom_target(self, url, category="social"):
        """Add a custom target URL to the appropriate category."""
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
            
        self.logger.info(f"Adding custom target to {category}: {url}")
        
        if category == "social":
            if url not in self.social_platforms:
                self.social_platforms.append(url)
        elif category == "photo":
            if url not in self.photo_sharing_sites:
                self.photo_sharing_sites.append(url)
        elif category == "community":
            if url not in self.community_sites:
                self.community_sites.append(url)
        
        return True
    
    def configure_sources(self, selected_sources):
        """Enable/disable source categories based on user selection."""
        # Map source keys to class attributes
        source_map = {
            "instagram": ["https://www.instagram.com/explore/tags/portrait/", 
                         "https://www.instagram.com/explore/tags/selfie/",
                         "https://www.instagram.com/explore/tags/people/"],
            "twitter": ["https://twitter.com/search?q=selfie&src=typed_query&f=image"],
            "pinterest": ["https://www.pinterest.com/search/pins/?q=people%20portrait"],
            "reddit": ["https://www.reddit.com/r/portraits/", 
                      "https://www.reddit.com/r/selfies/",
                      "https://www.reddit.com/r/humanporn/"],
            "flickr": ["https://www.flickr.com/groups/portraits/pool/",
                      "https://www.flickr.com/search/?text=portrait%20people&view_all=1"],
            "community": ["https://medium.com/search?q=portrait",
                         "https://wordpress.com/tag/portrait",
                         "https://tumblr.com/tagged/portrait",
                         "https://www.deviantart.com/tag/portrait"]
        }
        
        # Reset all source lists
        self.social_platforms = []
        self.photo_sharing_sites = []
        self.community_sites = []
        
        # Only include sources that are explicitly selected
        for source in selected_sources:
            if source in source_map:
                if source == "community":
                    self.community_sites.extend(source_map[source])
                else:
                    # All other sources (instagram, twitter, etc.) go into social platforms
                    self.social_platforms.extend(source_map[source])
        
        # Only include photo sharing sites if explicitly selected
        # Currently not in UI but can be added as a separate option
        if "photo" in selected_sources:
            self.photo_sharing_sites = [
                "https://500px.com/search?q=portrait&type=photos",
                "https://www.smugmug.com/search/?q=portrait&type=images",
                "https://unsplash.com/s/photos/people",
                "https://www.pexels.com/search/people/",
                "https://pixabay.com/images/search/people/"
            ]
        
        self.logger.info(f"Configured sources: Social platforms: {len(self.social_platforms)}, "
                        f"Photo sharing: {len(self.photo_sharing_sites)}, "
                        f"Community: {len(self.community_sites)}")