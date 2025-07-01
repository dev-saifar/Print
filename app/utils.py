import os
import PyPDF2
from PIL import Image
import logging
from datetime import datetime
from . import db
from .models import PrintJob, User

ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'png', 'jpg', 'jpeg', 'gif', 'txt'}

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_file_pages(filepath):
    """Get number of pages in a file"""
    try:
        ext = filepath.rsplit('.', 1)[1].lower()
        
        if ext == 'pdf':
            with open(filepath, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                return len(pdf_reader.pages)
        elif ext in ['png', 'jpg', 'jpeg', 'gif']:
            # Images are considered 1 page
            return 1
        elif ext in ['doc', 'docx']:
            # Estimate pages for doc files (rough estimate)
            file_size = os.path.getsize(filepath)
            estimated_pages = max(1, file_size // 5000)  # Rough estimate
            return estimated_pages
        elif ext == 'txt':
            # Estimate pages for text files
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as file:
                lines = len(file.readlines())
                return max(1, lines // 50)  # Assume 50 lines per page
        else:
            return 1
    except Exception as e:
        logging.error(f"Error getting page count for {filepath}: {e}")
        return 1

def process_print_job(job_id):
    """Process print job (Linux compatible simulation)"""
    try:
        from .models import PrintJob, User
        from datetime import datetime
        import time
        from flask import current_app
        
        # Get app instance and create context
        app = current_app._get_current_object()
        with app.app_context():
            job = PrintJob.query.get(job_id)
            if not job or job.status != 'pending':
                return

            file_path = job.file_path
            if not os.path.exists(file_path):
                job.status = 'failed'
                job.notes = 'File not found'
                db.session.commit()
                return

            # Update job status
            job.status = 'printing'
            job.started_at = datetime.utcnow()
            db.session.commit()

            # Simulate printing process
            try:
                time.sleep(2)  # Simulate printing time
                job.status = 'completed'
                job.completed_at = datetime.utcnow()
                logging.info(f"Print job {job_id} completed successfully")
            except Exception as e:
                job.status = 'failed'
                job.notes = f'Print error: {str(e)}'

            # Deduct cost
            user = User.query.get(job.user_id)
            if user and user.balance >= job.total_cost:
                user.balance -= job.total_cost
                user.quota_used += (job.total_pages * job.copies)
            else:
                job.status = 'failed'
                job.notes = 'Insufficient balance'

            db.session.commit()

    except Exception as e:
        logging.error(f"Error processing print job {job_id}: {e}")
        try:
            from . import app
            with app.app_context():
                job = PrintJob.query.get(job_id)
                if job:
                    job.status = 'failed'
                    job.notes = f'Unhandled exception: {str(e)}'
                    db.session.commit()
        except:
            pass
def get_windows_printers():
    """Get available printers (Linux compatible simulation)"""
    # Return simulated printer list for demo purposes
    return [
        'HP LaserJet Pro M404dn',
        'Canon imageCLASS MF445dw', 
        'Xerox WorkCentre 6515',
        'Default Printer'
    ]

def calculate_environmental_impact(pages):
    """Calculate environmental impact of printing"""
    # Rough estimates
    co2_per_page = 4.6  # grams of CO2 per page
    water_per_page = 10  # ml of water per page  
    trees_per_page = 0.006  # trees per page (very rough)
    
    return {
        'co2_grams': pages * co2_per_page,
        'water_ml': pages * water_per_page,
        'trees': pages * trees_per_page
    }

def format_file_size(size_bytes):
    """Format file size in human readable format"""
    if size_bytes == 0:
        return "0B"
    size_names = ["B", "KB", "MB", "GB"]
    import math
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return f"{s} {size_names[i]}"

def get_printer_status():
    """Simulate printer status"""
    import random
    printers = [
        {'name': 'HP LaserJet Pro 1', 'status': 'online', 'toner': random.randint(20, 100)},
        {'name': 'Canon ImageRunner 2', 'status': 'online', 'toner': random.randint(20, 100)},
        {'name': 'Xerox WorkCentre 3', 'status': 'offline', 'toner': random.randint(0, 100)},
    ]
    return printers
