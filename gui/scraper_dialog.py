import tkinter as tk
from tkinter import ttk, messagebox
import threading
import asyncio
import sys
import os
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
            
            # Get database and cropped face folders
            db_folder = self.config.get('Paths', 'DatabaseFolder', fallback="data/database")
            cropped_face_folder = self.config.get('Paths', 'CroppedFaceFolder', fallback="data/cropped_faces")
            
            # Initialize face encoder
            from processing.face_encoder import FaceEncoder
            face_encoder = FaceEncoder(source_folder, db_folder, cropped_face_folder)
            
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
                batch_stats = self._process_image_batch(face_encoder, batch_files, min_face_size, skip_existing, move_processed)
                
                # Update statistics
                for key in batch_stats:
                    if key in stats:
                        stats[key] += batch_stats[key]
                
                # Update UI
                progress = (i + len(batch_files)) / len(image_files) * 100
                self._update_progress(progress)
                self._update_stats(stats)
                self._update_ui(f"Processed batch {i//batch_size + 1}/{(len(image_files) + batch_size - 1)//batch_size}. Found {batch_stats['faces_found']} faces.")
            
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
    
    def _process_image_batch(self, face_encoder, image_files, min_face_size, skip_existing, move_processed):
        """Process a batch of images and return statistics."""
        batch_stats = {
            'processed_images': 0,
            'faces_found': 0,
            'faces_added': 0,
            'skipped_images': 0,
            'error_images': 0
        }
        
        for img_path in image_files:
            try:
                # Process the image
                _, face_data_list = face_encoder.process_image(img_path)
                batch_stats['processed_images'] += 1
                
                if face_data_list:
                    # Filter faces by size if needed
                    if min_face_size > 0:
                        face_data_list = [f for f in face_data_list if self._check_face_size(f, min_face_size)]
                    
                    batch_stats['faces_found'] += len(face_data_list)
                    batch_stats['faces_added'] += len(face_data_list)  # Assuming all found faces are added
                else:
                    # No faces found
                    if move_processed:
                        # Create path using os.path functions consistently
                        img_dir = os.path.dirname(img_path)
                        img_filename = os.path.basename(img_path)
                        no_faces_dir = os.path.join(img_dir, "no_faces")
                        os.makedirs(no_faces_dir, exist_ok=True)
                        
                        try:
                            dest_path = os.path.join(no_faces_dir, img_filename)
                            if os.path.exists(dest_path):
                                os.remove(dest_path)
                            os.rename(img_path, dest_path)
                        except Exception as e:
                            self.logger.error(f"Error moving file {img_path}: {e}")
            except Exception as e:
                self.logger.error(f"Error processing image {img_path}: {e}")
                batch_stats['error_images'] += 1
        
        return batch_stats
    
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