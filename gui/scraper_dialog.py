import tkinter as tk
from tkinter import ttk, messagebox
import threading
import asyncio
import sys
from utils.logger import get_logger

class ScraperDialog:
    """
    Dialog for controlling the web scraper functionality.
    """
    
    def __init__(self, parent, scraper_callback):
        """
        Initialize the scraper dialog.
        
        Args:
            parent: Parent window.
            scraper_callback: Callback function to run the scraper.
        """
        self.logger = get_logger(__name__)
        self.parent = parent
        self.scraper_callback = scraper_callback
        
        # Create a new top-level window
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Web Scraper")
        self.dialog.geometry("600x500")
        self.dialog.resizable(True, True)
        
        # Make it modal
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Create the UI elements
        self._create_ui()
        
        # Initialize state
        self.scraper_running = False
        self.scraper_thread = None
    
    def _create_ui(self):
        """Create the UI elements for the dialog."""
        # Main frame
        main_frame = ttk.Frame(self.dialog, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # URL input
        url_frame = ttk.Frame(main_frame)
        url_frame.pack(fill=tk.X, pady=5)
        
        url_label = ttk.Label(url_frame, text="Start URL:")
        url_label.pack(side=tk.LEFT, padx=5)
        
        self.url_entry = ttk.Entry(url_frame, width=50)
        self.url_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.url_entry.insert(0, "https://")
        
        # Options frame
        options_frame = ttk.LabelFrame(main_frame, text="Options", padding=10)
        options_frame.pack(fill=tk.X, pady=10)
        
        # Max pages option
        max_pages_frame = ttk.Frame(options_frame)
        max_pages_frame.pack(fill=tk.X, pady=5)
        
        max_pages_label = ttk.Label(max_pages_frame, text="Max Pages:")
        max_pages_label.pack(side=tk.LEFT, padx=5)
        
        self.max_pages_var = tk.StringVar(value="1000")
        max_pages_entry = ttk.Entry(max_pages_frame, textvariable=self.max_pages_var, width=10)
        max_pages_entry.pack(side=tk.LEFT, padx=5)
        
        # Batch size option
        batch_frame = ttk.Frame(options_frame)
        batch_frame.pack(fill=tk.X, pady=5)
        
        batch_label = ttk.Label(batch_frame, text="Batch Size:")
        batch_label.pack(side=tk.LEFT, padx=5)
        
        self.batch_size_var = tk.StringVar(value="1000")
        batch_entry = ttk.Entry(batch_frame, textvariable=self.batch_size_var, width=10)
        batch_entry.pack(side=tk.LEFT, padx=5)
        
        # Skip options
        skip_frame = ttk.Frame(options_frame)
        skip_frame.pack(fill=tk.X, pady=5)
        
        self.skip_crawl_var = tk.BooleanVar(value=False)
        skip_crawl_check = ttk.Checkbutton(
            skip_frame, 
            text="Skip Crawling (Use existing state)",
            variable=self.skip_crawl_var
        )
        skip_crawl_check.pack(side=tk.LEFT, padx=5)
        
        self.skip_download_var = tk.BooleanVar(value=False)
        skip_download_check = ttk.Checkbutton(
            skip_frame, 
            text="Skip Downloading",
            variable=self.skip_download_var
        )
        skip_download_check.pack(side=tk.LEFT, padx=20)
        
        # Log frame
        log_frame = ttk.LabelFrame(main_frame, text="Log", padding=10)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # Log text area
        self.log_text = tk.Text(log_frame, height=10, width=70, wrap=tk.WORD)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Add scrollbar to log text
        scrollbar = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.config(yscrollcommand=scrollbar.set)
        
        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)
        
        # Progress bar
        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(
            button_frame, 
            variable=self.progress_var,
            mode='indeterminate',
            length=300
        )
        self.progress_bar.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        # Start button
        self.start_button = ttk.Button(
            button_frame, 
            text="Start Scraper",
            command=self.start_scraper
        )
        self.start_button.pack(side=tk.LEFT, padx=5)
        
        # Close button
        self.close_button = ttk.Button(
            button_frame, 
            text="Close",
            command=self.close
        )
        self.close_button.pack(side=tk.LEFT, padx=5)
    
    def log(self, message):
        """
        Add a message to the log text area.
        
        Args:
            message (str): Message to add to the log.
        """
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
    
    def start_scraper(self):
        """Start the scraper in a separate thread."""
        if self.scraper_running:
            messagebox.showwarning(
                "Scraper Already Running",
                "The scraper is already running. Please wait for it to complete."
            )
            return
        
        # Get input values
        url = self.url_entry.get().strip()
        
        if not self.skip_crawl_var.get() and (not url or url == "https://"):
            messagebox.showerror(
                "Invalid URL",
                "Please enter a valid starting URL."
            )
            return
        
        try:
            max_pages = int(self.max_pages_var.get()) if self.max_pages_var.get() else None
            batch_size = int(self.batch_size_var.get()) if self.batch_size_var.get() else 1000
        except ValueError:
            messagebox.showerror(
                "Invalid Input",
                "Max pages and batch size must be valid integers."
            )
            return
        
        # Prepare the UI for scraping
        self.scraper_running = True
        self.start_button.config(state="disabled")
        self.progress_bar.start(10)
        self.log("Starting scraper...")
        
        # Create and start the scraper thread
        self.scraper_thread = threading.Thread(
            target=self._run_scraper,
            args=(
                url,
                max_pages,
                batch_size,
                self.skip_crawl_var.get(),
                self.skip_download_var.get()
            )
        )
        self.scraper_thread.daemon = True
        self.scraper_thread.start()
    
    def _run_scraper(self, url, max_pages, batch_size, skip_crawl, skip_download):
        """
        Run the scraper in a separate thread.
        
        Args:
            url (str): Starting URL.
            max_pages (int): Maximum number of pages to crawl.
            batch_size (int): Batch size for downloading.
            skip_crawl (bool): Whether to skip crawling.
            skip_download (bool): Whether to skip downloading.
        """
        try:
            # Create a new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # Run the scraper
            image_urls, stats = loop.run_until_complete(
                self.scraper_callback(
                    url,
                    max_pages,
                    batch_size,
                    skip_crawl,
                    skip_download
                )
            )
            
            # Report success
            self._update_ui(
                f"Scraper completed successfully.\n"
                f"Found {len(image_urls)} images.\n"
                f"Downloaded {stats.get('successful', 0)} of {stats.get('total', 0)} images.\n"
                f"Failed: {stats.get('failed', 0)}"
            )
            
        except Exception as e:
            # Report error
            self._update_ui(f"Error: {str(e)}")
            self.logger.error(f"Scraper error: {e}", exc_info=True)
        finally:
            # Clean up
            self._update_ui("Scraper operation complete.")
            self._update_ui_state(False)
    
    def _update_ui(self, message):
        """
        Update the UI from the scraper thread.
        
        Args:
            message (str): Message to log.
        """
        if self.dialog.winfo_exists():
            self.dialog.after(0, self.log, message)
    
    def _update_ui_state(self, running):
        """
        Update the UI state from the scraper thread.
        
        Args:
            running (bool): Whether the scraper is running.
        """
        if self.dialog.winfo_exists():
            def update():
                self.scraper_running = running
                self.start_button.config(state="normal" if not running else "disabled")
                if not running:
                    self.progress_bar.stop()
            
            self.dialog.after(0, update)
    
    def close(self):
        """Close the dialog."""
        if self.scraper_running:
            if messagebox.askyesno(
                "Confirm Close",
                "The scraper is still running. Are you sure you want to close this window?"
            ):
                self.dialog.destroy()
        else:
            self.dialog.destroy()