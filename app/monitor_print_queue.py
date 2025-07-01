import win32print
import win32api
import time
import os
import logging
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

SPOOL_DIR = r"C:\Windows\System32\spool\PRINTERS"

class SpoolMonitor(FileSystemEventHandler):
    def on_created(self, event):
        if event.is_directory:
            return
        if event.src_path.endswith((".spl", ".shd")):
            logging.info(f"New print job file detected: {event.src_path}")
            # You can log it to DB, read metadata or mark for holding
            # You can rename it or move to staging folder
            # Real-time print job capture (advanced: parse .shd)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
    observer = Observer()
    event_handler = SpoolMonitor()
    observer.schedule(event_handler, path=SPOOL_DIR, recursive=False)
    observer.start()

    logging.info("Monitoring Windows print spooler...")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
