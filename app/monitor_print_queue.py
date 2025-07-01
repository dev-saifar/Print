import time
import os
import logging
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Linux CUPS spool directory (common location)
SPOOL_DIR = "/var/spool/cups"

class SpoolMonitor(FileSystemEventHandler):
    def on_created(self, event):
        if event.is_directory:
            return
        if event.src_path.endswith((".pdf", ".ps", ".txt")):
            logging.info(f"New print job file detected: {event.src_path}")
            # Log to database or handle print job processing
            # This is a Linux-compatible print monitoring simulation

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
    
    # Check if spool directory exists, use fallback for demo
    spool_path = SPOOL_DIR if os.path.exists(SPOOL_DIR) else "/tmp/print_spool"
    os.makedirs(spool_path, exist_ok=True)
    
    observer = Observer()
    event_handler = SpoolMonitor()
    observer.schedule(event_handler, path=spool_path, recursive=False)
    observer.start()

    logging.info(f"Monitoring print spooler at {spool_path}...")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
