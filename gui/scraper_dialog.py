import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import asyncio
import sys
import os
import time
import json
import tempfile
from utils.logger import get_logger
from processing.face_encoder import FaceEncoder
from utils.config import Config

class ScraperDialog:
    """
    Dialog for controlling the web scraper functionality with improved integration.
    """
    
    def __init__(self, parent, scraper_callback, processor_callback=None):
        """
        Initialize the scraper dialog.
        
        Args:
            parent: Parent window.
            scraper_callback: Callback function to run the scraper.
            processor_callback: Callback function to process images.
        """
        self.logger = get_logger(__name__)
        self.parent = parent
        self.scraper_callback = scraper_callback
        self.processor_callback = processor_callback
        self.config = Config()
        self.auto_mode_running = False
        self.target_selector = None
        self.person_scraper = None
        
        # Create a new top-level window
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Web Scraper")
        self.dialog.geometry("700x600")
        self.dialog.resizable(True, True)
        
        # Make it modal
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Create the UI elements
        self._create_ui()
        
        # Initialize state
        self.scraper_running = False
        self.processor_running = False
        self.scraper_thread = None
        
        # Path to last downloaded images (used for processing)
        self.last_download_path = None
        self.download_stats = None
    
    def _create_ui(self):
        """Create the UI elements for the dialog."""
        # Main frame
        main_frame = ttk.Frame(self.dialog, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Notebook for tabbed interface
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Create tabs
        self.crawl_tab = ttk.Frame(self.notebook)
        self.process_tab = ttk.Frame(self.notebook)
        self.history_tab = ttk.Frame(self.notebook)
        
        self.notebook.add(self.crawl_tab, text="  Crawl & Download  ")
        self.notebook.add(self.process_tab, text="  Process Images  ")
        self.notebook.add(self.history_tab, text="  History  ")
        
        # Create content for tabs
        self._create_crawl_tab()
        self._create_process_tab()
        self._create_history_tab()
        
        # Add automatic mode tab
        self.auto_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.auto_tab, text="  Automatic Mode  ")
        self._create_auto_tab()
        
        # Log frame (below tabs)
        log_frame = ttk.LabelFrame(main_frame, text="Log", padding=10)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # Log text area
        self.log_text = tk.Text(log_frame, height=10, width=70, wrap=tk.WORD)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Add scrollbar to log text
        scrollbar = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.config(yscrollcommand=scrollbar.set)
        
        # Status frame
        status_frame = ttk.Frame(main_frame)
        status_frame.pack(fill=tk.X, pady=5)
        
        # Status label
        self.status_label = ttk.Label(status_frame, text="Ready")
        self.status_label.pack(side=tk.LEFT, padx=5)
        
        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=5)
        
        # Close button
        self.close_button = ttk.Button(
            button_frame, 
            text="Close",
            command=self.close
        )
        self.close_button.pack(side=tk.RIGHT, padx=5)
        
        # Version label
        version_label = ttk.Label(button_frame, text="v1.1")
        version_label.pack(side=tk.LEFT, padx=5)
    
    def _create_crawl_tab(self):
        """Create the crawl and download tab content."""
        # URL input
        url_frame = ttk.Frame(self.crawl_tab, padding=5)
        url_frame.pack(fill=tk.X, pady=5)
        
        url_label = ttk.Label(url_frame, text="Start URL:")
        url_label.pack(side=tk.LEFT, padx=5)
        
        self.url_entry = ttk.Entry(url_frame, width=50)
        self.url_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # Load from config if available
        start_url = self.config.get('Scraper', 'StartURL', fallback="https://")
        self.url_entry.insert(0, start_url)
        
        # Batch name
        batch_name_frame = ttk.Frame(self.crawl_tab, padding=5)
        batch_name_frame.pack(fill=tk.X, pady=5)
        
        batch_name_label = ttk.Label(batch_name_frame, text="Batch Name:")
        batch_name_label.pack(side=tk.LEFT, padx=5)
        
        self.batch_name_var = tk.StringVar()
        self.batch_name_entry = ttk.Entry(batch_name_frame, textvariable=self.batch_name_var, width=30)
        self.batch_name_entry.pack(side=tk.LEFT, padx=5)
        
        # Auto-generate batch name button
        self.gen_name_button = ttk.Button(
            batch_name_frame,
            text="Generate",
            command=self._generate_batch_name
        )
        self.gen_name_button.pack(side=tk.LEFT, padx=5)
        
        # Options frame
        options_frame = ttk.LabelFrame(self.crawl_tab, text="Crawl Options", padding=10)
        options_frame.pack(fill=tk.X, pady=10)
        
        # Max pages option
        max_pages_frame = ttk.Frame(options_frame)
        max_pages_frame.pack(fill=tk.X, pady=5)
        
        max_pages_label = ttk.Label(max_pages_frame, text="Max Pages:")
        max_pages_label.pack(side=tk.LEFT, padx=5)
        
        self.max_pages_var = tk.StringVar(value=self.config.get('Scraper', 'MaxPagesToVisit', fallback="1000"))
        max_pages_entry = ttk.Entry(max_pages_frame, textvariable=self.max_pages_var, width=10)
        max_pages_entry.pack(side=tk.LEFT, padx=5)
        
        # Max images option
        max_images_frame = ttk.Frame(options_frame)
        max_images_frame.pack(fill=tk.X, pady=5)
        
        max_images_label = ttk.Label(max_images_frame, text="Max Images:")
        max_images_label.pack(side=tk.LEFT, padx=5)
        
        self.max_images_var = tk.StringVar(value="10000")
        max_images_entry = ttk.Entry(max_images_frame, textvariable=self.max_images_var, width=10)
        max_images_entry.pack(side=tk.LEFT, padx=5)
        
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
        
        # Auto-process option
        process_frame = ttk.Frame(options_frame)
        process_frame.pack(fill=tk.X, pady=5)
        
        self.auto_process_var = tk.BooleanVar(value=True)
        auto_process_check = ttk.Checkbutton(
            process_frame, 
            text="Automatically process images after download",
            variable=self.auto_process_var
        )
        auto_process_check.pack(side=tk.LEFT, padx=5)
        
        # Progress indicator
        progress_frame = ttk.Frame(self.crawl_tab)
        progress_frame.pack(fill=tk.X, pady=10)
        
        self.crawl_progress_var = tk.DoubleVar(value=0)
        self.crawl_progress_bar = ttk.Progressbar(
            progress_frame, 
            variable=self.crawl_progress_var,
            mode='indeterminate',
            length=400
        )
        self.crawl_progress_bar.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        # Start button
        self.start_button = ttk.Button(
            progress_frame, 
            text="Start Scraper",
            command=self.start_scraper
        )
        self.start_button.pack(side=tk.LEFT, padx=5)
    
    def _create_process_tab(self):
        """Create the process tab content."""
        # Source folder frame
        folder_frame = ttk.Frame(self.process_tab, padding=5)
        folder_frame.pack(fill=tk.X, pady=5)
        
        folder_label = ttk.Label(folder_frame, text="Image Folder:")
        folder_label.pack(side=tk.LEFT, padx=5)
        
        self.folder_var = tk.StringVar(value=self.config.get('Paths', 'DownloadFolder', fallback="data/downloaded_images"))
        folder_entry = ttk.Entry(folder_frame, textvariable=self.folder_var, width=40)
        folder_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        browse_button = ttk.Button(
            folder_frame,
            text="Browse",
            command=self._browse_folder
        )
        browse_button.pack(side=tk.LEFT, padx=5)
        
        # Processing options frame
        proc_options_frame = ttk.LabelFrame(self.process_tab, text="Processing Options", padding=10)
        proc_options_frame.pack(fill=tk.X, pady=10)
        
        # Min face size
        face_size_frame = ttk.Frame(proc_options_frame)
        face_size_frame.pack(fill=tk.X, pady=5)
        
        min_face_label = ttk.Label(face_size_frame, text="Minimum Face Size (pixels):")
        min_face_label.pack(side=tk.LEFT, padx=5)
        
        self.min_face_var = tk.StringVar(value="50")
        min_face_entry = ttk.Entry(face_size_frame, textvariable=self.min_face_var, width=10)
        min_face_entry.pack(side=tk.LEFT, padx=5)
        
        # Skip existing
        skip_existing_frame = ttk.Frame(proc_options_frame)
        skip_existing_frame.pack(fill=tk.X, pady=5)
        
        self.skip_existing_var = tk.BooleanVar(value=True)
        skip_existing_check = ttk.Checkbutton(
            skip_existing_frame, 
            text="Skip existing images",
            variable=self.skip_existing_var
        )
        skip_existing_check.pack(side=tk.LEFT, padx=5)
        
        # Move processed
        move_processed_frame = ttk.Frame(proc_options_frame)
        move_processed_frame.pack(fill=tk.X, pady=5)
        
        self.move_processed_var = tk.BooleanVar(value=True)
        move_processed_check = ttk.Checkbutton(
            move_processed_frame, 
            text="Move processed images to sorted folders",
            variable=self.move_processed_var
        )
        move_processed_check.pack(side=tk.LEFT, padx=5)
        
        # Process in batches
        batch_process_frame = ttk.Frame(proc_options_frame)
        batch_process_frame.pack(fill=tk.X, pady=5)
        
        self.batch_process_var = tk.BooleanVar(value=True)
        batch_process_check = ttk.Checkbutton(
            batch_process_frame, 
            text="Process in batches",
            variable=self.batch_process_var
        )
        batch_process_check.pack(side=tk.LEFT, padx=5)
        
        batch_size_label = ttk.Label(batch_process_frame, text="Batch Size:")
        batch_size_label.pack(side=tk.LEFT, padx=(20, 5))
        
        self.proc_batch_size_var = tk.StringVar(value="50")
        proc_batch_size_entry = ttk.Entry(batch_process_frame, textvariable=self.proc_batch_size_var, width=10)
        proc_batch_size_entry.pack(side=tk.LEFT, padx=5)
        
        # Progress indicator
        proc_progress_frame = ttk.Frame(self.process_tab)
        proc_progress_frame.pack(fill=tk.X, pady=10)
        
        self.process_progress_var = tk.DoubleVar(value=0)
        self.process_progress_bar = ttk.Progressbar(
            proc_progress_frame, 
            variable=self.process_progress_var,
            mode='determinate',
            length=400
        )
        self.process_progress_bar.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        # Start process button
        self.process_button = ttk.Button(
            proc_progress_frame, 
            text="Process Images",
            command=self.start_processor
        )
        self.process_button.pack(side=tk.LEFT, padx=5)
        
        # Statistics frame
        stats_frame = ttk.LabelFrame(self.process_tab, text="Processing Statistics", padding=10)
        stats_frame.pack(fill=tk.X, pady=10)
        
        # Statistics labels
        stats_grid = ttk.Frame(stats_frame)
        stats_grid.pack(fill=tk.X, pady=5)
        
        # Row 1
        ttk.Label(stats_grid, text="Total Images:").grid(row=0, column=0, padx=5, pady=2, sticky="w")
        self.total_images_label = ttk.Label(stats_grid, text="0")
        self.total_images_label.grid(row=0, column=1, padx=5, pady=2, sticky="w")
        
        ttk.Label(stats_grid, text="Processed:").grid(row=0, column=2, padx=5, pady=2, sticky="w")
        self.processed_images_label = ttk.Label(stats_grid, text="0")
        self.processed_images_label.grid(row=0, column=3, padx=5, pady=2, sticky="w")
        
        # Row 2
        ttk.Label(stats_grid, text="Faces Found:").grid(row=1, column=0, padx=5, pady=2, sticky="w")
        self.faces_found_label = ttk.Label(stats_grid, text="0")
        self.faces_found_label.grid(row=1, column=1, padx=5, pady=2, sticky="w")
        
        ttk.Label(stats_grid, text="Added to DB:").grid(row=1, column=2, padx=5, pady=2, sticky="w")
        self.faces_added_label = ttk.Label(stats_grid, text="0")
        self.faces_added_label.grid(row=1, column=3, padx=5, pady=2, sticky="w")
        
        # Row 3
        ttk.Label(stats_grid, text="Skipped:").grid(row=2, column=0, padx=5, pady=2, sticky="w")
        self.skipped_images_label = ttk.Label(stats_grid, text="0")
        self.skipped_images_label.grid(row=2, column=1, padx=5, pady=2, sticky="w")
        
        ttk.Label(stats_grid, text="Errors:").grid(row=2, column=2, padx=5, pady=2, sticky="w")
        self.error_images_label = ttk.Label(stats_grid, text="0")
        self.error_images_label.grid(row=2, column=3, padx=5, pady=2, sticky="w")
    
    def _create_history_tab(self):
        """Create the history tab content."""
        # Tree view for batch history
        tree_frame = ttk.Frame(self.history_tab, padding=5)
        tree_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Create treeview
        columns = ("date", "batch_name", "images", "faces", "status")
        self.history_tree = ttk.Treeview(tree_frame, columns=columns, show="headings")
        
        # Define headings
        self.history_tree.heading("date", text="Date")
        self.history_tree.heading("batch_name", text="Batch Name")
        self.history_tree.heading("images", text="Images")
        self.history_tree.heading("faces", text="Faces")
        self.history_tree.heading("status", text="Status")
        
        # Define columns
        self.history_tree.column("date", width=150)
        self.history_tree.column("batch_name", width=200)
        self.history_tree.column("images", width=80, anchor="center")
        self.history_tree.column("faces", width=80, anchor="center")
        self.history_tree.column("status", width=100)
        
        # Add a scrollbar
        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.history_tree.yview)
        self.history_tree.configure(yscrollcommand=scrollbar.set)
        
        # Pack the tree and scrollbar
        self.history_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Bind double-click event
        self.history_tree.bind("<Double-1>", self._on_history_double_click)
        
        # Buttons frame
        history_buttons_frame = ttk.Frame(self.history_tab, padding=5)
        history_buttons_frame.pack(fill=tk.X, pady=5)
        
        # Refresh button
        refresh_button = ttk.Button(
            history_buttons_frame,
            text="Refresh",
            command=self._load_history
        )
        refresh_button.pack(side=tk.LEFT, padx=5)
        
        # Process button
        process_selected_button = ttk.Button(
            history_buttons_frame,
            text="Process Selected",
            command=self._process_selected_batch
        )
        process_selected_button.pack(side=tk.LEFT, padx=5)
        
        # Delete button
        delete_button = ttk.Button(
            history_buttons_frame,
            text="Delete Selected",
            command=self._delete_selected_batch
        )
        delete_button.pack(side=tk.LEFT, padx=5)
        
        # Populate the history
        self._load_history()
    
    def _generate_batch_name(self):
        """Generate a batch name based on the URL."""
        url = self.url_entry.get().strip()
        if url and url != "https://":
            try:
                from urllib.parse import urlparse
                parsed = urlparse(url)
                domain = parsed.netloc
                if domain:
                    import time
                    timestamp = time.strftime("%Y%m%d")
                    batch_name = f"{domain}_{timestamp}"
                    self.batch_name_var.set(batch_name)
                    return
            except Exception as e:
                self.logger.error(f"Error generating batch name: {e}")
        
        # Default if URL parsing fails
        import time
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        self.batch_name_var.set(f"batch_{timestamp}")
    
    def _browse_folder(self):
        """Browse for an image folder."""
        from tkinter import filedialog
        folder = filedialog.askdirectory(
            initialdir=self.folder_var.get(),
            title="Select Image Folder"
        )
        if folder:
            self.folder_var.set(folder)
    
    def _load_history(self):
        """Load batch history from records."""
        # Clear existing items
        for item in self.history_tree.get_children():
            self.history_tree.delete(item)
        
        # Get history directory
        history_dir = os.path.join(
            self.config.get('Paths', 'DatabaseFolder', fallback="data/database"),
            "history"
        )
        
        # Ensure history directory exists
        os.makedirs(history_dir, exist_ok=True)
        
        # Check for history files
        try:
            import json
            import glob
            
            history_files = glob.glob(os.path.join(history_dir, "*.json"))
            history_items = []
            
            for file_path in history_files:
                try:
                    with open(file_path, 'r') as f:
                        batch_data = json.load(f)
                        
                    # Extract data for display
                    date = batch_data.get('date', 'Unknown')
                    batch_name = batch_data.get('batch_name', os.path.basename(file_path))
                    images = batch_data.get('images', {}).get('total', 0)
                    faces = batch_data.get('faces', {}).get('total', 0)
                    status = batch_data.get('status', 'Unknown')
                    
                    history_items.append((date, batch_name, images, faces, status, file_path))
                except Exception as e:
                    self.logger.error(f"Error loading history file {file_path}: {e}")
            
            # Sort by date (newest first)
            history_items.sort(reverse=True)
            
            # Add to treeview
            for date, batch_name, images, faces, status, file_path in history_items:
                self.history_tree.insert("", "end", values=(date, batch_name, images, faces, status), tags=(file_path,))
                
        except Exception as e:
            self.logger.error(f"Error loading history: {e}")
    
    def _on_history_double_click(self, event):
        """Handle double-click on history item."""
        item = self.history_tree.selection()[0]
        values = self.history_tree.item(item, "values")
        if values:
            batch_name = values[1]
            messagebox.showinfo("Batch Details", f"Selected batch: {batch_name}\n\nDouble-click to view details or select an action from the buttons below.")
    
    def _process_selected_batch(self):
        """Process the selected batch from history."""
        selected = self.history_tree.selection()
        if not selected:
            messagebox.showwarning("No Selection", "Please select a batch to process.")
            return
        
        item = selected[0]
        values = self.history_tree.item(item, "values")
        tags = self.history_tree.item(item, "tags")
        
        if values and tags:
            batch_name = values[1]
            history_file = tags[0]
            
            try:
                import json
                with open(history_file, 'r') as f:
                    batch_data = json.load(f)
                
                # Get download folder from batch data
                download_dir = batch_data.get('download_dir')
                if not download_dir or not os.path.exists(download_dir):
                    messagebox.showerror("Error", f"Download directory not found: {download_dir}")
                    return
                
                # Set folder and switch to process tab
                self.folder_var.set(download_dir)
                self.notebook.select(self.process_tab)
                
                # Ask to start processing
                if messagebox.askyesno("Process Batch", f"Start processing images from batch '{batch_name}'?"):
                    self.start_processor()
                    
            except Exception as e:
                self.logger.error(f"Error processing batch: {e}")
                messagebox.showerror("Error", f"Error processing batch: {e}")
    
    def _delete_selected_batch(self):
        """Delete the selected batch history."""
        selected = self.history_tree.selection()
        if not selected:
            messagebox.showwarning("No Selection", "Please select a batch to delete.")
            return
            
        item = selected[0]
        values = self.history_tree.item(item, "values")
        tags = self.history_tree.item(item, "tags")
        
        if values and tags:
            batch_name = values[1]
            history_file = tags[0]
            
            if messagebox.askyesno("Confirm Delete", f"Delete history for batch '{batch_name}'?\n\nThis will only remove the history record, not the actual images or database entries."):
                try:
                    os.remove(history_file)
                    self._load_history()  # Refresh the list
                except Exception as e:
                    self.logger.error(f"Error deleting history file: {e}")
                    messagebox.showerror("Error", f"Error deleting history: {e}")
    
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
        batch_name = self.batch_name_var.get().strip()
        
        if not self.skip_crawl_var.get() and (not url or url == "https://"):
            messagebox.showerror(
                "Invalid URL",
                "Please enter a valid starting URL."
            )
            return
        
        if not batch_name:
            # Auto-generate a batch name if none provided
            self._generate_batch_name()
            batch_name = self.batch_name_var.get().strip()
        
        try:
            max_pages = int(self.max_pages_var.get()) if self.max_pages_var.get() else None
            max_images = int(self.max_images_var.get()) if self.max_images_var.get() else None
            batch_size = int(self.batch_size_var.get()) if self.batch_size_var.get() else 1000
        except ValueError:
            messagebox.showerror(
                "Invalid Input",
                "Max pages, max images, and batch size must be valid integers."
            )
            return
        
        # Prepare the UI for scraping
        self.scraper_running = True
        self.start_button.config(state="disabled")
        self.crawl_progress_bar.start(10)
        self.status_label.config(text="Scraping in progress...")
        self.log("Starting scraper...")
        
        # Create and start the scraper thread
        self.scraper_thread = threading.Thread(
            target=self._run_scraper,
            args=(
                url,
                max_pages,
                max_images,
                batch_size,
                batch_name,
                self.skip_crawl_var.get(),
                self.skip_download_var.get()
            )
        )
        self.scraper_thread.daemon = True
        self.scraper_thread.start()
    
    def start_processor(self):
        """Start processing images in a separate thread."""
        if self.processor_running:
            messagebox.showwarning(
                "Processor Already Running",
                "The image processor is already running. Please wait for it to complete."
            )
            return
        
        # Get the source folder
        source_folder = self.folder_var.get().strip()
        if not source_folder or not os.path.exists(source_folder):
            messagebox.showerror(
                "Invalid Folder",
                "Please enter a valid image folder path."
            )
            return
        
        try:
            min_face_size = int(self.min_face_var.get()) if self.min_face_var.get() else 50
            batch_size = int(self.proc_batch_size_var.get()) if self.proc_batch_size_var.get() else 50
        except ValueError:
            messagebox.showerror(
                "Invalid Input",
                "Minimum face size and batch size must be valid integers."
            )
            return
        
        # Prepare the UI for processing
        self.processor_running = True
        self.process_button.config(state="disabled")
        self.process_progress_bar.config(mode="indeterminate")
        self.process_progress_bar.start(10)
        self.status_label.config(text="Processing images...")
        self.log("Starting image processing...")
        
        # Reset statistics
        self.total_images_label.config(text="0")
        self.processed_images_label.config(text="0")
        self.faces_found_label.config(text="0")
        self.faces_added_label.config(text="0")
        self.skipped_images_label.config(text="0")
        self.error_images_label.config(text="0")
        
        # Create and start the processor thread
        processor_thread = threading.Thread(
            target=self._run_processor,
            args=(
                source_folder,
                min_face_size,
                batch_size,
                self.skip_existing_var.get(),
                self.move_processed_var.get()
            )
        )
        processor_thread.daemon = True
        processor_thread.start()
    
    def _run_scraper(self, url, max_pages, max_images, batch_size, batch_name, skip_crawl, skip_download):
        """
        Run the scraper in a separate thread.
        
        Args:
            url (str): Starting URL.
            max_pages (int): Maximum number of pages to crawl.
            max_images (int): Maximum number of images to download.
            batch_size (int): Batch size for downloading.
            batch_name (str): Name for the batch.
            skip_crawl (bool): Whether to skip crawling.
            skip_download (bool): Whether to skip downloading.
        """
        try:
            # Create a new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # Prepare custom download directory if batch name provided
            download_dir = self.config.get('Paths', 'DownloadFolder', fallback="data/downloaded_images")
            if batch_name:
                import time
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                download_dir = os.path.join(download_dir, f"{batch_name}_{timestamp}")
            
            # Run the scraper
            image_urls, stats = loop.run_until_complete(
                self.scraper_callback(
                    url,
                    max_pages,
                    max_images,
                    batch_size,
                    download_dir,
                    skip_crawl,
                    skip_download
                )
            )
            
            # Save batch info to history
            self._save_batch_history(batch_name, download_dir, image_urls, stats)
            
            # Store the download directory for later processing
            self.last_download_path = download_dir
            self.download_stats = stats
            
            # Report success
            self._update_ui(
                f"Scraper completed successfully.\n"
                f"Found {len(image_urls)} images.\n"
                f"Downloaded {stats.get('successful', 0)} of {stats.get('total', 0)} images.\n"
                f"Failed: {stats.get('failed', 0)}"
            )
            
            # Auto-process if selected and images were downloaded
            if (not skip_download and 
                stats.get('successful', 0) > 0 and 
                self.auto_process_var.get() and 
                os.path.exists(download_dir)):
                
                self._update_ui("Starting automatic processing of downloaded images...")
                
                # Switch to the process tab
                self.dialog.after(0, self.notebook.select, self.process_tab)
                
                # Set the folder and start processing
                self.dialog.after(0, self.folder_var.set, download_dir)
                self.dialog.after(100, self.start_processor)
            
        except Exception as e:
            # Report error
            self._update_ui(f"Error: {str(e)}")
            self.logger.error(f"Scraper error: {e}", exc_info=True)
        finally:
            # Clean up
            self._update_ui("Scraper operation complete.")
            self._update_ui_state(False)
    
    def _run_processor(self, source_folder, min_face_size, batch_size, skip_existing, move_processed):
        """
        Run the image processor in a separate thread.
        
        Args:
            source_folder (str): Folder containing images to process.
            min_face_size (int): Minimum face size in pixels.
            batch_size (int): Size of batches for processing.
            skip_existing (bool): Whether to skip existing images.
            move_processed (bool): Whether to move processed images.
        """
        try:
            # Set up statistics tracking
            stats = {
                'total_images': 0,
                'processed_images': 0,
                'faces_found': 0,
                'faces_added': 0,
                'skipped_images': 0,
                'error_images': 0
            }
            
            # Get database and cropped face folders with absolute paths
            db_folder = os.path.abspath(self.config.get('Paths', 'DatabaseFolder', fallback="data/database"))
            cropped_face_folder = os.path.abspath(self.config.get('Paths', 'CroppedFaceFolder', fallback="data/cropped_faces"))
            source_folder = os.path.abspath(source_folder)
            
            # Ensure directories exist
            os.makedirs(db_folder, exist_ok=True)
            os.makedirs(cropped_face_folder, exist_ok=True)
            
            self.logger.info(f"Processing images from: {source_folder}")
            self.logger.info(f"Database folder: {db_folder}")
            self.logger.info(f"Cropped faces folder: {cropped_face_folder}")
            
            # Initialize face encoder
            from processing.face_encoder import FaceEncoder
            face_encoder = FaceEncoder(
                img_folder=source_folder,
                db_path=db_folder,
                cropped_face_folder=cropped_face_folder
            )
            
            # Get list of image files
            image_files = []
            for ext in ['.jpg', '.jpeg', '.png', '.bmp']:
                image_files.extend(self._find_files(source_folder, ext))
            
            stats['total_images'] = len(image_files)
            self._update_stats(stats)
            
            # Display determinate progress if we know the total
            self.dialog.after(0, self._set_process_progress_mode, "determinate")
            
            # Process images in batches
            for i in range(0, len(image_files), batch_size):
                # Stop if dialog was closed
                if not hasattr(self, 'dialog') or not self.dialog.winfo_exists():
                    break
                    
                # Get batch of files
                batch_files = image_files[i:i+batch_size]
                
                # Process the batch
                face_buffer = []
                for img_path in batch_files:
                    try:
                        # Normalize path for Windows
                        img_path = os.path.normpath(os.path.abspath(img_path))
                        
                        # Skip if already processed and skip_existing is True
                        if skip_existing and face_encoder._is_face_in_database(img_path):
                            stats['skipped_images'] += 1
                            continue
                        
                        # Process the image
                        _, face_data_list = face_encoder.process_image(img_path)
                        stats['processed_images'] += 1
                        
                        if face_data_list:
                            # Filter faces by size if needed
                            if min_face_size > 0:
                                face_data_list = [f for f in face_data_list if self._check_face_size(f, min_face_size)]
                            
                            face_buffer.extend(face_data_list)
                            stats['faces_found'] += len(face_data_list)
                            stats['faces_added'] += len(face_data_list)
                            
                            # Move to faces folder if requested
                            if move_processed:
                                try:
                                    faces_dir = os.path.join(os.path.dirname(img_path), "faces")
                                    os.makedirs(faces_dir, exist_ok=True)
                                    dest_path = os.path.join(faces_dir, os.path.basename(img_path))
                                    if os.path.exists(dest_path):
                                        os.remove(dest_path)
                                    os.rename(img_path, dest_path)
                                except Exception as e:
                                    self.logger.error(f"Error moving file to faces folder: {e}")
                        else:
                            # No faces found
                            if move_processed:
                                try:
                                    no_faces_dir = os.path.join(os.path.dirname(img_path), "no_faces")
                                    os.makedirs(no_faces_dir, exist_ok=True)
                                    dest_path = os.path.join(no_faces_dir, os.path.basename(img_path))
                                    if os.path.exists(dest_path):
                                        os.remove(dest_path)
                                    os.rename(img_path, dest_path)
                                except Exception as e:
                                    self.logger.error(f"Error moving file to no_faces folder: {e}")
                    except Exception as e:
                        self.logger.error(f"Error processing image {img_path}: {e}")
                        stats['error_images'] += 1
                
                # Save the batch to database if we have faces
                if face_buffer:
                    try:
                        # Generate timestamp-based filename
                        timestamp = int(time.time())
                        db_filename = f"face_data_batch_{timestamp}.json"
                        db_file_path = os.path.join(db_folder, db_filename)
                        
                        # Save using atomic write pattern
                        with tempfile.NamedTemporaryFile('w', delete=False, dir=db_folder, suffix='.json') as tmp_file:
                            json.dump(face_buffer, tmp_file, indent=2)
                            tmp_file.flush()
                            os.fsync(tmp_file.fileno())
                            tmp_path = tmp_file.name
                        
                        # Rename temp file to final filename
                        if os.path.exists(db_file_path):
                            os.remove(db_file_path)
                        os.rename(tmp_path, db_file_path)
                        
                        self.logger.info(f"Saved {len(face_buffer)} faces to {db_file_path}")
                    except Exception as e:
                        self.logger.error(f"Error saving face data to database: {e}")
                        stats['faces_added'] -= len(face_buffer)
                
                # Update UI
                progress = (i + len(batch_files)) / len(image_files) * 100
                self._update_progress(progress)
                self._update_stats(stats)
                self._update_ui(f"Processed batch {i//batch_size + 1}/{(len(image_files) + batch_size - 1)//batch_size}. Found {stats['faces_found']} faces.")
            
            # Verify database after processing
            self.logger.info("Verifying database...")
            db_stats = face_encoder.verify_database()
            self._update_ui(
                f"Database verification:\n"
                f"- Total files: {db_stats['total_files']}\n"
                f"- Valid files: {db_stats['valid_files']}\n"
                f"- Total faces: {db_stats['total_faces']}\n"
                f"- Corrupted files: {db_stats['corrupted_files']}"
            )
            
            # Final report
            self._update_ui(
                f"Processing completed:\n"
                f"Processed {stats['processed_images']} of {stats['total_images']} images.\n"
                f"Found {stats['faces_found']} faces, added {stats['faces_added']} to database.\n"
                f"Skipped: {stats['skipped_images']}, Errors: {stats['error_images']}"
            )
            
        except Exception as e:
            self._update_ui(f"Processing error: {str(e)}")
            self.logger.error(f"Image processor error: {e}", exc_info=True)
        finally:
            self.dialog.after(0, self._processing_complete)
    
    def _find_files(self, directory, extension):
        """Find files with the given extension in the directory and subdirectories."""
        files = []
        for root, _, filenames in os.walk(directory):
            for filename in filenames:
                if filename.lower().endswith(extension.lower()):
                    files.append(os.path.join(root, filename))
        return files
    
    def _check_face_size(self, face_data, min_size):
        """Check if a face meets the minimum size requirement."""
        if 'bbox' in face_data:
            bbox = face_data['bbox']
            width = bbox[2] - bbox[0]
            height = bbox[3] - bbox[1]
            return width >= min_size and height >= min_size
        return True  # If no bbox, assume it's valid
    
    def _update_progress(self, value):
        """Update the progress bar."""
        self.dialog.after(0, self.process_progress_var.set, value)
    
    def _update_stats(self, stats):
        """Update the statistics labels."""
        def update():
            self.total_images_label.config(text=str(stats['total_images']))
            self.processed_images_label.config(text=str(stats['processed_images']))
            self.faces_found_label.config(text=str(stats['faces_found']))
            self.faces_added_label.config(text=str(stats['faces_added']))
            self.skipped_images_label.config(text=str(stats['skipped_images']))
            self.error_images_label.config(text=str(stats['error_images']))
        
        self.dialog.after(0, update)
    
    def _set_process_progress_mode(self, mode):
        """Set the progress bar mode."""
        if mode == "determinate":
            self.process_progress_bar.stop()
            self.process_progress_bar.config(mode="determinate")
        else:
            self.process_progress_bar.config(mode="indeterminate")
            self.process_progress_bar.start(10)
    
    def _processing_complete(self):
        """Update the UI when processing is complete."""
        self.processor_running = False
        self.process_button.config(state="normal")
        self.process_progress_bar.stop()
        self.process_progress_bar.config(value=100)
        self.status_label.config(text="Processing complete")
        
        # Refresh history
        self._load_history()
    
    def _save_batch_history(self, batch_name, download_dir, image_urls, stats):
        """Save batch history to a file."""
        try:
            # Ensure history directory exists
            history_dir = os.path.join(
                self.config.get('Paths', 'DatabaseFolder', fallback="data/database"),
                "history"
            )
            os.makedirs(history_dir, exist_ok=True)
            
            # Create batch record
            import json
            import time
            
            batch_data = {
                'batch_name': batch_name,
                'date': time.strftime("%Y-%m-%d %H:%M:%S"),
                'timestamp': time.time(),
                'download_dir': download_dir,
                'images': {
                    'total': stats.get('total', len(image_urls)),
                    'successful': stats.get('successful', 0),
                    'failed': stats.get('failed', 0)
                },
                'faces': {
                    'total': 0,  # Will be updated after processing
                    'added': 0
                },
                'status': 'Downloaded'
            }
            
            # Save to file
            filename = f"batch_{int(time.time())}.json"
            file_path = os.path.join(history_dir, filename)
            
            with open(file_path, 'w') as f:
                json.dump(batch_data, f, indent=2)
                
            # Refresh history
            self.dialog.after(0, self._load_history)
            
        except Exception as e:
            self.logger.error(f"Error saving batch history: {e}")
    
    def _update_ui(self, message):
        """
        Update the UI from the scraper thread.
        
        Args:
            message (str): Message to log.
        """
        if hasattr(self, 'dialog') and self.dialog.winfo_exists():
            self.dialog.after(0, self.log, message)
    
    def _update_ui_state(self, running):
        """
        Update the UI state from the scraper thread.
        
        Args:
            running (bool): Whether the scraper is running.
        """
        if hasattr(self, 'dialog') and self.dialog.winfo_exists():
            def update():
                self.scraper_running = running
                self.start_button.config(state="normal" if not running else "disabled")
                if not running:
                    self.crawl_progress_bar.stop()
                    self.status_label.config(text="Ready")
            
            self.dialog.after(0, update)
    
    def close(self):
        """Close the dialog."""
        if self.scraper_running or self.processor_running:
            if messagebox.askyesno(
                "Confirm Close",
                "There are operations in progress. Are you sure you want to close this window?"
            ):
                self.dialog.destroy()
        else:
            self.dialog.destroy()

    def _create_auto_tab(self):
        """Create the automatic mode tab content for social media focus."""
        # Main frame
        auto_frame = ttk.Frame(self.auto_tab, padding=5)
        auto_frame.pack(fill=tk.X, pady=5)
        
        # Title
        title_label = ttk.Label(
            auto_frame, 
            text="Automatic Social Media Photo Collector",
            font=("Helvetica", 12, "bold")
        )
        title_label.pack(pady=10)
        
        description_label = ttk.Label(
            auto_frame,
            text="This tool automatically collects public photos of people from social media and photo sharing sites.",
            wraplength=500
        )
        description_label.pack(pady=5)
        
        # Settings frame
        settings_frame = ttk.LabelFrame(auto_frame, text="Collection Settings", padding=10)
        settings_frame.pack(fill=tk.X, pady=10)
        
        # Target count
        target_frame = ttk.Frame(settings_frame)
        target_frame.pack(fill=tk.X, pady=5)
        
        target_label = ttk.Label(target_frame, text="Target Face Count:")
        target_label.pack(side=tk.LEFT, padx=5)
        
        self.target_count_var = tk.StringVar(value="500")
        target_entry = ttk.Entry(target_frame, textvariable=self.target_count_var, width=10)
        target_entry.pack(side=tk.LEFT, padx=5)
        
        # Maximum runtime
        runtime_frame = ttk.Frame(settings_frame)
        runtime_frame.pack(fill=tk.X, pady=5)
        
        runtime_label = ttk.Label(runtime_frame, text="Maximum Runtime (minutes):")
        runtime_label.pack(side=tk.LEFT, padx=5)
        
        self.max_runtime_var = tk.StringVar(value="60")
        runtime_entry = ttk.Entry(runtime_frame, textvariable=self.max_runtime_var, width=10)
        runtime_entry.pack(side=tk.LEFT, padx=5)
        
        # Source selection frame
        source_frame = ttk.LabelFrame(auto_frame, text="Source Selection", padding=10)
        source_frame.pack(fill=tk.X, pady=10)
        
        # Source options
        sources = [
            ("Instagram Public Tags", "instagram"),
            ("Twitter Public Photos", "twitter"),
            ("Pinterest Boards", "pinterest"),
            ("Flickr Public", "flickr"),
            ("Reddit Public", "reddit"),
            ("Public Photo Communities", "community"),
            ("Photo Sharing Sites", "photo")
        ]
        
        self.source_vars = {}
        for text, value in sources:
            var = tk.BooleanVar(value=True)
            self.source_vars[value] = var
            ttk.Checkbutton(
                source_frame,
                text=text,
                variable=var
            ).pack(anchor=tk.W, padx=5, pady=2)
        
        # Custom URL
        custom_frame = ttk.Frame(source_frame)
        custom_frame.pack(fill=tk.X, pady=10)
        
        custom_label = ttk.Label(custom_frame, text="Add Custom URL:")
        custom_label.pack(side=tk.LEFT, padx=5)
        
        self.custom_url_var = tk.StringVar()
        custom_entry = ttk.Entry(custom_frame, textvariable=self.custom_url_var, width=40)
        custom_entry.pack(side=tk.LEFT, padx=5)
        
        add_button = ttk.Button(
            custom_frame,
            text="Add",
            command=self._add_custom_url
        )
        add_button.pack(side=tk.LEFT, padx=5)
        
        # Progress and status
        progress_frame = ttk.Frame(auto_frame)
        progress_frame.pack(fill=tk.X, pady=10)
        
        self.auto_progress_var = tk.DoubleVar(value=0)
        self.auto_progress_bar = ttk.Progressbar(
            progress_frame,
            variable=self.auto_progress_var,
            mode='determinate',
            length=400
        )
        self.auto_progress_bar.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        # Start button
        self.auto_start_button = ttk.Button(
            progress_frame,
            text="Start Social Media Collector",
            command=self.start_automatic_mode
        )
        self.auto_start_button.pack(side=tk.LEFT, padx=5)
        
        # Status Frame
        status_frame = ttk.LabelFrame(auto_frame, text="Collection Status", padding=10)
        status_frame.pack(fill=tk.X, pady=10)
        
        # Status grid
        status_grid = ttk.Frame(status_frame)
        status_grid.pack(fill=tk.X, pady=5)
        
        # Row 1
        ttk.Label(status_grid, text="Faces Collected:").grid(row=0, column=0, padx=5, pady=2, sticky="w")
        self.faces_collected_label = ttk.Label(status_grid, text="0")
        self.faces_collected_label.grid(row=0, column=1, padx=5, pady=2, sticky="w")
        
        ttk.Label(status_grid, text="Images Processed:").grid(row=0, column=2, padx=5, pady=2, sticky="w")
        self.images_processed_label = ttk.Label(status_grid, text="0")
        self.images_processed_label.grid(row=0, column=3, padx=5, pady=2, sticky="w")
        
        # Row 2
        ttk.Label(status_grid, text="Sites Visited:").grid(row=1, column=0, padx=5, pady=2, sticky="w")
        self.sites_visited_label = ttk.Label(status_grid, text="0")
        self.sites_visited_label.grid(row=1, column=1, padx=5, pady=2, sticky="w")
        
        ttk.Label(status_grid, text="Elapsed Time:").grid(row=1, column=2, padx=5, pady=2, sticky="w")
        self.elapsed_time_label = ttk.Label(status_grid, text="00:00:00")
        self.elapsed_time_label.grid(row=1, column=3, padx=5, pady=2, sticky="w")
        
        # Row 3
        ttk.Label(status_grid, text="Current Source:").grid(row=2, column=0, padx=5, pady=2, sticky="w")
        self.current_source_label = ttk.Label(status_grid, text="None")
        self.current_source_label.grid(row=2, column=1, columnspan=3, padx=5, pady=2, sticky="w")
        
        # Add Instagram specific section
        instagram_frame = ttk.LabelFrame(auto_frame, text="Instagram Profile Scraping", padding=10)
        instagram_frame.pack(fill=tk.X, pady=10)
        
        # Profile count
        profile_frame = ttk.Frame(instagram_frame)
        profile_frame.pack(fill=tk.X, pady=5)
        
        profile_label = ttk.Label(profile_frame, text="Profiles to Find:")
        profile_label.pack(side=tk.LEFT, padx=5)
        
        self.profile_count_var = tk.StringVar(value="200")
        profile_entry = ttk.Entry(profile_frame, textvariable=self.profile_count_var, width=10)
        profile_entry.pack(side=tk.LEFT, padx=5)
        
        # Profiles to scrape
        scrape_frame = ttk.Frame(instagram_frame)
        scrape_frame.pack(fill=tk.X, pady=5)
        
        scrape_label = ttk.Label(scrape_frame, text="Profiles to Scrape:")
        scrape_label.pack(side=tk.LEFT, padx=5)
        
        self.scrape_count_var = tk.StringVar(value="50")
        scrape_entry = ttk.Entry(scrape_frame, textvariable=self.scrape_count_var, width=10)
        scrape_entry.pack(side=tk.LEFT, padx=5)
        
        # Images per profile
        images_frame = ttk.Frame(instagram_frame)
        images_frame.pack(fill=tk.X, pady=5)
        
        images_label = ttk.Label(images_frame, text="Images per Profile:")
        images_label.pack(side=tk.LEFT, padx=5)
        
        self.images_per_profile_var = tk.StringVar(value="10")
        images_entry = ttk.Entry(images_frame, textvariable=self.images_per_profile_var, width=10)
        images_entry.pack(side=tk.LEFT, padx=5)
        
        # Instagram button
        instagram_button_frame = ttk.Frame(instagram_frame)
        instagram_button_frame.pack(fill=tk.X, pady=10)
        
        self.instagram_button = ttk.Button(
            instagram_button_frame,
            text="Run Instagram Scraper",
            command=self.start_instagram_scraper
        )
        self.instagram_button.pack(side=tk.RIGHT, padx=5)
        
        # Add Twitter button
        self.twitter_button = ttk.Button(
            instagram_button_frame,
            text="Run Twitter Scraper",
            command=self.start_twitter_scraper
        )
        self.twitter_button.pack(side=tk.RIGHT, padx=5)
        
        # Show profiles button
        self.show_profiles_button = ttk.Button(
            instagram_button_frame,
            text="Show Discovered Profiles",
            command=self._show_instagram_profiles
        )
        self.show_profiles_button.pack(side=tk.LEFT, padx=5)

    def _add_custom_url(self):
        """Add a custom URL to the target list."""
        url = self.custom_url_var.get().strip()
        if not url:
            return
            
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
            
        # Check if target selector initialized
        if not hasattr(self, 'target_selector') or self.target_selector is None:
            from scraper.social_media_target import SocialMediaTargetSelector
            self.target_selector = SocialMediaTargetSelector()
        
        # Add to the appropriate category
        self.target_selector.add_custom_target(url, "social")
        
        # Confirm to user
        self.custom_url_var.set("")
        self.log(f"Added custom URL: {url}")

    def start_automatic_mode(self):
        """Start the automatic social media scraping mode."""
        if self.auto_mode_running:
            messagebox.showwarning(
                "Automatic Mode Running",
                "Automatic mode is already running. Please wait for it to complete."
            )
            return
        
        # Get input values
        try:
            target_face_count = int(self.target_count_var.get())
            max_runtime = int(self.max_runtime_var.get())
            
            if target_face_count <= 0 or max_runtime <= 0:
                raise ValueError("Values must be positive numbers")
        except ValueError as e:
            messagebox.showerror(
                "Invalid Input",
                f"Please enter valid settings: {str(e)}"
            )
            return
        
        # Get selected sources
        selected_sources = [source for source, var in self.source_vars.items() if var.get()]
        if not selected_sources:
            messagebox.showerror(
                "No Sources Selected",
                "Please select at least one source category."
            )
            return
        
        # Prepare UI for scraping
        self.auto_mode_running = True
        self.auto_start_button.config(state="disabled")
        self.auto_progress_bar.config(mode="indeterminate")
        self.auto_progress_bar.start(10)
        self.status_label.config(text="Social media scraping in progress...")
        self.log("Starting automatic social media photo collection...")
        
        # Reset statistics
        self.faces_collected_label.config(text="0")
        self.images_processed_label.config(text="0")
        self.sites_visited_label.config(text="0")
        self.elapsed_time_label.config(text="00:00:00")
        self.current_source_label.config(text="Initializing...")
        
        # Initialize progress updater
        self.start_time = time.time()
        self.update_id = self.dialog.after(1000, self._update_elapsed_time)
        
        # Create and start the thread
        auto_thread = threading.Thread(
            target=self._run_social_scraper,
            args=(
                target_face_count,
                max_runtime,
                selected_sources
            )
        )
        auto_thread.daemon = True
        auto_thread.start()

    def _update_elapsed_time(self):
        """Update the elapsed time display."""
        if not hasattr(self, 'start_time') or not self.auto_mode_running:
            return
        
        elapsed = time.time() - self.start_time
        hours = int(elapsed // 3600)
        minutes = int((elapsed % 3600) // 60)
        seconds = int(elapsed % 60)
        
        time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        self.elapsed_time_label.config(text=time_str)
        
        # Continue updating if still running
        if self.auto_mode_running:
            self.update_id = self.dialog.after(1000, self._update_elapsed_time)

    def _run_social_scraper(self, target_face_count, max_runtime, selected_sources):
        """Run the social media scraper in a separate thread."""
        try:
            # Import modules here to avoid circular imports
            from scraper.social_media_target import SocialMediaTargetSelector
            from scraper.automatic_scraper import AutomaticPersonScraper
            
            # Get database and download paths
            db_path = self.config.get('Paths', 'DatabaseFolder', fallback="data/database")
            download_dir = self.config.get('Paths', 'DownloadFolder', fallback="data/downloaded_images")
            social_download_dir = os.path.join(download_dir, f"social_media_{int(time.time())}")
            
            # Initialize the target selector and configure sources
            self.target_selector = SocialMediaTargetSelector()
            self.target_selector.configure_sources(selected_sources)
            
            # Log detailed information about configured sources
            self._log_configured_sources(self.target_selector)
            
            # Initialize the scraper with the configured target selector
            self.person_scraper = AutomaticPersonScraper(
                db_path=db_path, 
                download_dir=social_download_dir,
                target_selector=self.target_selector
            )
            
            # Set up asyncio loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # Variables for status updates
            face_count = 0
            images_processed = 0
            sites_visited = 0
            current_source = "Starting..."
            
            # Define the update function
            def update_status(stats):
                nonlocal face_count, images_processed, sites_visited, current_source
                face_count = stats.get('face_count', 0)
                images_processed = stats.get('images_processed', 0)
                sites_visited = stats.get('sites_visited', 0)
                current_source = stats.get('current_source', current_source)
                
                self.dialog.after(0, self._update_social_status, 
                                face_count, images_processed, 
                                sites_visited, current_source)
            
            # Run the scraper
            results = loop.run_until_complete(self.person_scraper.run_automatic_mode(
                target_face_count=target_face_count,
                max_runtime_minutes=max_runtime
            ))
            
            # Final update
            update_status(results)
            
            # Report success
            self._update_ui(
                f"Social media collection completed.\n"
                f"Collected {results.get('face_count', 0)} of {target_face_count} target faces.\n"
                f"Processed {results.get('images_processed', 0)} images from {results.get('sites_visited', 0)} sites.\n"
                f"Total runtime: {results.get('runtime_seconds', 0)/60:.1f} minutes"
            )
            
        except Exception as e:
            # Report error
            self._update_ui(f"Error in social media collection: {str(e)}")
            self.logger.error(f"Social scraper error: {e}", exc_info=True)
        finally:
            # Clean up
            if hasattr(self, 'update_id'):
                self.dialog.after_cancel(self.update_id)
            self._update_ui("Social media collection complete.")
            self.dialog.after(0, self._auto_mode_complete)

    def _update_social_status(self, face_count, images_processed, sites_visited, current_source):
        """Update the social scraper status UI."""
        self.faces_collected_label.config(text=str(face_count))
        self.images_processed_label.config(text=str(images_processed))
        self.sites_visited_label.config(text=str(sites_visited))
        self.current_source_label.config(text=current_source)
        
        # Update progress based on target
        progress = min(100, (face_count / int(self.target_count_var.get())) * 100)
        self.auto_progress_bar.stop()
        self.auto_progress_bar.config(mode="determinate")
        self.auto_progress_var.set(progress)

    def _auto_mode_complete(self):
        """Update the UI when automatic mode is complete."""
        self.auto_mode_running = False
        self.auto_start_button.config(state="normal")
        self.auto_progress_bar.stop()
        self.auto_progress_bar.config(value=100)
        self.status_label.config(text="Automatic mode complete")
        
        # Refresh history
        self._load_history()

    def _log_configured_sources(self, target_selector):
        """Log detailed information about configured sources."""
        # Get the first few URLs from each source to log (for debugging)
        social_urls = target_selector.social_platforms[:2] if target_selector.social_platforms else []
        photo_urls = target_selector.photo_sharing_sites[:2] if target_selector.photo_sharing_sites else []
        community_urls = target_selector.community_sites[:2] if target_selector.community_sites else []
        
        # Add ellipsis if there are more URLs
        if len(target_selector.social_platforms) > 2:
            social_urls.append("...")
        if len(target_selector.photo_sharing_sites) > 2:
            photo_urls.append("...")
        if len(target_selector.community_sites) > 2:
            community_urls.append("...")
            
        # Log source counts and examples
        self.logger.info(f"Configured social platforms ({len(target_selector.social_platforms)}): {social_urls}")
        self.logger.info(f"Configured photo sites ({len(target_selector.photo_sharing_sites)}): {photo_urls}")
        self.logger.info(f"Configured community sites ({len(target_selector.community_sites)}): {community_urls}")
        
        # Also update the status message in the UI
        platforms_text = f"Social: {len(target_selector.social_platforms)}, "
        platforms_text += f"Photo: {len(target_selector.photo_sharing_sites)}, "
        platforms_text += f"Community: {len(target_selector.community_sites)}"
        self._update_ui(f"Configured source counts: {platforms_text}")

    def start_instagram_scraper(self):
        """Start the Instagram profile discovery and scraping process."""
        if self.auto_mode_running:
            messagebox.showwarning(
                "Process Running",
                "Another automatic scraping process is already running. Please wait for it to complete."
            )
            return
        
        # Get input values
        try:
            profile_count = int(self.profile_count_var.get())
            scrape_count = int(self.scrape_count_var.get())
            images_per_profile = int(self.images_per_profile_var.get())
            
            if profile_count <= 0 or scrape_count <= 0 or images_per_profile <= 0:
                raise ValueError("Values must be positive numbers")
                
            if scrape_count > profile_count:
                scrape_count = profile_count
                self.scrape_count_var.set(str(scrape_count))
        except ValueError as e:
            messagebox.showerror(
                "Invalid Input",
                f"Please enter valid settings: {str(e)}"
            )
            return
        
        # Prepare UI for scraping
        self.auto_mode_running = True
        self.instagram_button.config(state="disabled")
        self.auto_progress_bar.config(mode="indeterminate")
        self.auto_progress_bar.start(10)
        self.status_label.config(text="Instagram scraping in progress...")
        self.log("Starting Instagram profile discovery and scraping...")
        
        # Reset statistics
        self.faces_collected_label.config(text="0")
        self.images_processed_label.config(text="0")
        self.sites_visited_label.config(text="0")
        self.current_source_label.config(text="Instagram")
        
        # Initialize progress updater
        self.start_time = time.time()
        self.update_id = self.dialog.after(1000, self._update_elapsed_time)
        
        # Create and start the thread
        instagram_thread = threading.Thread(
            target=self._run_instagram_scraper,
            args=(
                profile_count,
                scrape_count,
                images_per_profile
            )
        )
        instagram_thread.daemon = True
        instagram_thread.start()

    def _run_instagram_scraper(self, profile_count, scrape_count, images_per_profile):
        """Run the Instagram scraper in a separate thread."""
        try:
            # Import the new Instagram controller
            from scraper.instagram_controller import scrape_instagram_profiles
            
            # Run the scraper using asyncio
            results = asyncio.run(scrape_instagram_profiles(
                profile_count=profile_count,
                max_profiles_to_scrape=scrape_count,
                max_images_per_profile=images_per_profile
            ))
            
            # Update UI with results
            self.dialog.after(0, self._update_instagram_status, 
                             results.get('faces_detected', 0),
                             results.get('images_downloaded', 0),
                             results.get('profiles_found', 0))
            
            # Report success
            self._update_ui(
                f"Instagram scraping completed.\n"
                f"Found {results.get('profiles_found', 0)} profiles.\n"
                f"Downloaded {results.get('images_downloaded', 0)} images.\n"
                f"Detected {results.get('faces_detected', 0)} faces.\n"
                f"Total runtime: {results.get('runtime_seconds', 0)/60:.1f} minutes"
            )
            
        except Exception as e:
            # Report error
            self._update_ui(f"Error in Instagram scraping: {str(e)}")
            self.logger.error(f"Instagram scraper error: {e}", exc_info=True)
        finally:
            # Clean up
            if hasattr(self, 'update_id'):
                self.dialog.after_cancel(self.update_id)
            self._update_ui("Instagram scraping complete.")
            self.dialog.after(0, self._instagram_scraping_complete)

    def _update_instagram_status(self, faces_count, images_count, profiles_count):
        """Update the Instagram scraper status UI."""
        self.faces_collected_label.config(text=str(faces_count))
        self.images_processed_label.config(text=str(images_count))
        self.sites_visited_label.config(text=str(profiles_count))
        
        # Update progress based on target
        progress = min(100, (faces_count / int(self.target_count_var.get())) * 100)
        self.auto_progress_bar.stop()
        self.auto_progress_bar.config(mode="determinate")
        self.auto_progress_var.set(progress)

    def _instagram_scraping_complete(self):
        """Update the UI when Instagram scraping is complete."""
        self.auto_mode_running = False
        self.instagram_button.config(state="normal")
        self.auto_progress_bar.stop()
        self.auto_progress_bar.config(value=100)
        self.status_label.config(text="Instagram scraping complete")
        
        # Refresh history
        self._load_history()

    def _show_instagram_profiles(self):
        """Show the list of discovered Instagram profiles."""
        profiles_file = "data/instagram_profiles.json"
        
        if not os.path.exists(profiles_file):
            messagebox.showinfo(
                "No Profiles Found",
                "No Instagram profiles have been discovered yet. Run the Instagram scraper first."
            )
            return
        
        try:
            with open(profiles_file, 'r') as f:
                data = json.load(f)
                
            if 'profiles' not in data or not data['profiles']:
                messagebox.showinfo(
                    "No Profiles Found",
                    "No Instagram profiles have been discovered yet. Run the Instagram scraper first."
                )
                return
            
            # Create a new window to display profiles
            profile_window = tk.Toplevel(self.dialog)
            profile_window.title("Discovered Instagram Profiles")
            profile_window.geometry("500x600")
            profile_window.transient(self.dialog)
            
            # Frame for the profile list
            frame = ttk.Frame(profile_window, padding=10)
            frame.pack(fill=tk.BOTH, expand=True)
            
            # Title
            ttk.Label(
                frame, 
                text=f"Discovered Instagram Profiles ({len(data['profiles'])})",
                font=("Helvetica", 12, "bold")
            ).pack(pady=10)
            
            # Last updated
            if 'last_updated' in data:
                ttk.Label(
                    frame,
                    text=f"Last Updated: {data['last_updated']}"
                ).pack(pady=5)
            
            # Create a Text widget with scrollbar
            profile_frame = ttk.Frame(frame)
            profile_frame.pack(fill=tk.BOTH, expand=True, pady=10)
            
            profile_text = tk.Text(profile_frame, wrap=tk.WORD, height=20, width=40)
            profile_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            
            scrollbar = ttk.Scrollbar(profile_frame, command=profile_text.yview)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            profile_text.config(yscrollcommand=scrollbar.set)
            
            # Insert profiles
            for profile in data['profiles']:
                profile_text.insert(tk.END, f"@{profile}\n")
            
            profile_text.config(state="disabled")  # Make read-only
            
            # Buttons
            button_frame = ttk.Frame(frame)
            button_frame.pack(fill=tk.X, pady=10)
            
            ttk.Button(
                button_frame,
                text="Close",
                command=profile_window.destroy
            ).pack(side=tk.RIGHT, padx=5)
            
            ttk.Button(
                button_frame,
                text="Open File Location",
                command=lambda: os.startfile(os.path.dirname(os.path.abspath(profiles_file)))
            ).pack(side=tk.LEFT, padx=5)
        except Exception as e:
            self.logger.error(f"Error showing Instagram profiles: {e}")
            messagebox.showerror(
                "Error",
                f"Failed to load Instagram profiles: {e}"
            )

    def start_twitter_scraper(self):
        """Start the Twitter profile discovery and scraping process."""
        if self.auto_mode_running:
            messagebox.showwarning(
                "Process Running",
                "Another automatic scraping process is already running. Please wait for it to complete."
            )
            return
        
        # Get input values
        try:
            profile_count = int(self.profile_count_var.get())
            scrape_count = int(self.scrape_count_var.get())
            images_per_profile = int(self.images_per_profile_var.get())
            
            if profile_count <= 0 or scrape_count <= 0 or images_per_profile <= 0:
                raise ValueError("Values must be positive numbers")
                
            if scrape_count > profile_count:
                scrape_count = profile_count
                self.scrape_count_var.set(str(scrape_count))
        except ValueError as e:
            messagebox.showerror(
                "Invalid Input",
                f"Please enter valid settings: {str(e)}"
            )
            return
        
        # Prepare UI for scraping
        self.auto_mode_running = True
        self.twitter_button.config(state="disabled")
        self.auto_progress_bar.config(mode="indeterminate")
        self.auto_progress_bar.start(10)
        self.status_label.config(text="Twitter scraping in progress...")
        self.log("Starting Twitter profile discovery and scraping...")
        
        # Reset statistics
        self.faces_collected_label.config(text="0")
        self.images_processed_label.config(text="0")
        self.sites_visited_label.config(text="0")
        self.current_source_label.config(text="Twitter")
        
        # Initialize progress updater
        self.start_time = time.time()
        self.update_id = self.dialog.after(1000, self._update_elapsed_time)
        
        # Create and start the thread
        twitter_thread = threading.Thread(
            target=self._run_twitter_scraper,
            args=(
                profile_count,
                scrape_count,
                images_per_profile
            )
        )
        twitter_thread.daemon = True
        twitter_thread.start()

    def _run_twitter_scraper(self, profile_count, scrape_count, images_per_profile):
        """Run the Twitter scraper in a separate thread."""
        try:
            # Import the new Twitter controller
            from scraper.twitter_controller import scrape_twitter_profiles
            
            # Run the scraper using asyncio
            results = asyncio.run(scrape_twitter_profiles(
                profile_count=profile_count,
                max_profiles_to_scrape=scrape_count,
                max_images_per_profile=images_per_profile
            ))
            
            # Update UI with results
            self.dialog.after(0, self._update_twitter_status, 
                             results.get('faces_detected', 0),
                             results.get('images_downloaded', 0),
                             results.get('profiles_found', 0))
            
            # Report success
            self._update_ui(
                f"Twitter scraping completed.\n"
                f"Found {results.get('profiles_found', 0)} profiles.\n"
                f"Downloaded {results.get('images_downloaded', 0)} images.\n"
                f"Detected {results.get('faces_detected', 0)} faces.\n"
                f"Total runtime: {results.get('runtime_seconds', 0)/60:.1f} minutes"
            )
            
        except Exception as e:
            # Report error
            self._update_ui(f"Error in Twitter scraping: {str(e)}")
            self.logger.error(f"Twitter scraper error: {e}", exc_info=True)
        finally:
            # Clean up
            if hasattr(self, 'update_id'):
                self.dialog.after_cancel(self.update_id)
            self._update_ui("Twitter scraping complete.")
            self.dialog.after(0, self._twitter_scraping_complete)

    def _update_twitter_status(self, faces_count, images_count, profiles_count):
        """Update the Twitter scraper status UI."""
        self.faces_collected_label.config(text=str(faces_count))
        self.images_processed_label.config(text=str(images_count))
        self.sites_visited_label.config(text=str(profiles_count))
        
        # Update progress based on target
        progress = min(100, (faces_count / int(self.target_count_var.get())) * 100)
        self.auto_progress_bar.stop()
        self.auto_progress_bar.config(mode="determinate")
        self.auto_progress_var.set(progress)

    def _twitter_scraping_complete(self):
        """Update the UI when Twitter scraping is complete."""
        self.auto_mode_running = False
        self.twitter_button.config(state="normal")
        self.auto_progress_bar.stop()
        self.auto_progress_bar.config(value=100)
        self.status_label.config(text="Twitter scraping complete")
        
        # Refresh history
        self._load_history()