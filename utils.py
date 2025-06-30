import os
import PyPDF2
from PIL import Image
import logging
from datetime import datetime
from app import db
from models import PrintJob, User

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
    """Simulate print job processing"""
    try:
        with db.app.app_context():
            job = PrintJob.query.get(job_id)
            if not job or job.status != 'pending':
                return
            
            # Update job status to printing
            job.status = 'printing'
            job.started_at = datetime.utcnow()
            db.session.commit()
            
            # Simulate printing time based on pages and priority
            import time
            processing_time = job.total_pages * job.copies * 0.5  # 0.5 seconds per page
            if job.priority == 'high':
                processing_time *= 0.7
            elif job.priority == 'low':
                processing_time *= 1.3
                
            time.sleep(min(processing_time, 30))  # Cap at 30 seconds for demo
            
            # Complete the job
            job.status = 'completed'
            job.completed_at = datetime.utcnow()
            
            # Deduct cost from user balance
            user = User.query.get(job.user_id)
            if user and user.balance >= job.total_cost:
                user.balance -= job.total_cost
                user.quota_used += (job.total_pages * job.copies)
            else:
                job.status = 'failed'
                job.notes = 'Insufficient balance'
            
            db.session.commit()
            logging.info(f"Print job {job_id} completed")
            
    except Exception as e:
        logging.error(f"Error processing print job {job_id}: {e}")
        with db.app.app_context():
            job = PrintJob.query.get(job_id)
            if job:
                job.status = 'failed'
                job.notes = f'Processing error: {str(e)}'
                db.session.commit()

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
