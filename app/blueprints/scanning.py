"""
Scanning Blueprint
Handles scan-to-email and scan-to-folder functionality
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_login import login_required, current_user
from datetime import datetime
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders

from .. import db
from ..models import User, Printer, ScanJob

scanning_bp = Blueprint('scanning', __name__, url_prefix='/scan')

class ScanJob(db.Model):
    """Track scanning operations"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    printer_id = db.Column(db.Integer, db.ForeignKey('printer.id'), nullable=False)
    
    # Scan settings
    scan_type = db.Column(db.String(20), default='pdf')  # pdf, jpeg, png, tiff
    resolution = db.Column(db.Integer, default=300)  # DPI
    color_mode = db.Column(db.String(20), default='color')  # color, grayscale, bw
    duplex = db.Column(db.Boolean, default=False)
    
    # Output settings
    destination_type = db.Column(db.String(20), nullable=False)  # email, folder, download
    destination_path = db.Column(db.String(500))  # email address or folder path
    
    # File info
    filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500))
    file_size = db.Column(db.Integer)
    page_count = db.Column(db.Integer, default=1)
    
    # Status
    status = db.Column(db.String(20), default='pending')  # pending, processing, completed, failed
    error_message = db.Column(db.Text)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)
    
    # Relationships
    user = db.relationship('User', backref='scan_jobs')
    printer = db.relationship('Printer', backref='scan_jobs')

@scanning_bp.route('/')
@login_required
def index():
    """Scanning dashboard"""
    recent_scans = ScanJob.query.filter_by(user_id=current_user.id)\
                                .order_by(ScanJob.created_at.desc())\
                                .limit(10).all()
    
    available_scanners = Printer.query.filter_by(supports_scanning=True, is_active=True).all()
    
    return render_template('scanning/index.html', 
                         recent_scans=recent_scans,
                         scanners=available_scanners)

@scanning_bp.route('/new/<int:scanner_id>')
@login_required
def new_scan(scanner_id):
    """Setup new scan job"""
    scanner = Printer.query.get_or_404(scanner_id)
    
    if not scanner.supports_scanning:
        flash('This device does not support scanning', 'error')
        return redirect(url_for('scanning.index'))
    
    # Get user's email destinations
    user_emails = [current_user.email]
    
    # Get available network folders (simulated)
    network_folders = [
        '/scans/users/' + current_user.username,
        '/scans/department/' + (current_user.department.name if current_user.department else 'general'),
        '/scans/shared'
    ]
    
    return render_template('scanning/new_scan.html',
                         scanner=scanner,
                         user_emails=user_emails,
                         network_folders=network_folders)

@scanning_bp.route('/start', methods=['POST'])
@login_required
def start_scan():
    """Start scanning process"""
    scanner_id = request.form.get('scanner_id')
    scanner = Printer.query.get_or_404(scanner_id)
    
    # Scan settings
    scan_type = request.form.get('scan_type', 'pdf')
    resolution = int(request.form.get('resolution', 300))
    color_mode = request.form.get('color_mode', 'color')
    duplex = request.form.get('duplex') == 'on'
    page_count = int(request.form.get('page_count', 1))
    
    # Destination settings
    destination_type = request.form.get('destination_type')
    destination_path = request.form.get('destination_path', '')
    
    # Create scan job
    filename = f"scan_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{scan_type}"
    
    scan_job = ScanJob(
        user_id=current_user.id,
        printer_id=scanner_id,
        scan_type=scan_type,
        resolution=resolution,
        color_mode=color_mode,
        duplex=duplex,
        destination_type=destination_type,
        destination_path=destination_path,
        filename=filename,
        page_count=page_count
    )
    
    db.session.add(scan_job)
    db.session.commit()
    
    # Process scan (simulation)
    success = process_scan_job(scan_job.id)
    
    if success:
        flash(f'Scan completed successfully: {filename}', 'success')
    else:
        flash('Scan failed. Please try again.', 'error')
    
    return redirect(url_for('scanning.job_status', job_id=scan_job.id))

@scanning_bp.route('/job/<int:job_id>')
@login_required
def job_status(job_id):
    """View scan job status"""
    job = ScanJob.query.get_or_404(job_id)
    
    if job.user_id != current_user.id and current_user.role != 'admin':
        flash('Access denied', 'error')
        return redirect(url_for('scanning.index'))
    
    return render_template('scanning/job_status.html', job=job)

def process_scan_job(job_id):
    """Process scan job - simulate actual scanning"""
    try:
        job = ScanJob.query.get(job_id)
        if not job:
            return False
        
        job.status = 'processing'
        db.session.commit()
        
        # Simulate scanning delay
        import time
        time.sleep(2)
        
        # Create simulated scan file
        scan_directory = os.path.join(current_app.config['UPLOAD_FOLDER'], 'scans')
        os.makedirs(scan_directory, exist_ok=True)
        
        file_path = os.path.join(scan_directory, job.filename)
        
        # Create dummy scan file (in production, this would be actual scan data)
        with open(file_path, 'w') as f:
            f.write(f"Simulated scan file\nScanner: {job.printer.name}\nUser: {job.user.username}\nPages: {job.page_count}\nResolution: {job.resolution} DPI\nColor Mode: {job.color_mode}")
        
        job.file_path = file_path
        job.file_size = os.path.getsize(file_path)
        
        # Process based on destination
        if job.destination_type == 'email':
            success = send_scan_email(job)
        elif job.destination_type == 'folder':
            success = save_scan_to_folder(job)
        else:  # download
            success = True  # File is ready for download
        
        if success:
            job.status = 'completed'
            job.completed_at = datetime.utcnow()
        else:
            job.status = 'failed'
            job.error_message = 'Failed to deliver scan to destination'
        
        db.session.commit()
        return success
        
    except Exception as e:
        job.status = 'failed'
        job.error_message = str(e)
        db.session.commit()
        return False

def send_scan_email(job):
    """Send scanned document via email"""
    try:
        # Email configuration (in production, use proper SMTP settings)
        smtp_server = "localhost"  # Simulated
        smtp_port = 587
        sender_email = "scans@biztra.com"
        sender_password = "password"  # Use environment variable in production
        
        # Create email message
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = job.destination_path
        msg['Subject'] = f"Scan from {job.printer.name} - {job.filename}"
        
        # Email body
        body = f"""
        Your scan has been completed.
        
        Details:
        - Scanned by: {job.user.username}
        - Scanner: {job.printer.name}
        - Pages: {job.page_count}
        - Resolution: {job.resolution} DPI
        - Color Mode: {job.color_mode}
        - File Type: {job.scan_type.upper()}
        
        Please find the scanned document attached.
        
        Best regards,
        Biztra Print Management System
        """
        
        msg.attach(MIMEText(body, 'plain'))
        
        # Attach scan file
        if job.file_path and os.path.exists(job.file_path):
            with open(job.file_path, "rb") as attachment:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(attachment.read())
                encoders.encode_base64(part)
                part.add_header(
                    'Content-Disposition',
                    f'attachment; filename= {job.filename}'
                )
                msg.attach(part)
        
        # Send email (simulated - in production, use actual SMTP)
        print(f"[EMAIL SIMULATION] Sending scan to {job.destination_path}")
        print(f"Subject: {msg['Subject']}")
        print(f"Attachment: {job.filename}")
        
        # In production:
        # server = smtplib.SMTP(smtp_server, smtp_port)
        # server.starttls()
        # server.login(sender_email, sender_password)
        # server.sendmail(sender_email, job.destination_path, msg.as_string())
        # server.quit()
        
        return True
        
    except Exception as e:
        print(f"Email sending failed: {e}")
        return False

def save_scan_to_folder(job):
    """Save scan to network folder"""
    try:
        # Create destination directory if it doesn't exist
        destination_dir = job.destination_path
        if not destination_dir.startswith('/'):
            # Relative path, make it absolute within scan directory
            scan_base = os.path.join(current_app.config['UPLOAD_FOLDER'], 'scans')
            destination_dir = os.path.join(scan_base, destination_dir.lstrip('/'))
        
        os.makedirs(destination_dir, exist_ok=True)
        
        # Copy scan file to destination
        import shutil
        destination_file = os.path.join(destination_dir, job.filename)
        shutil.copy2(job.file_path, destination_file)
        
        print(f"[FOLDER SIMULATION] Saved scan to {destination_file}")
        return True
        
    except Exception as e:
        print(f"Folder save failed: {e}")
        return False

@scanning_bp.route('/download/<int:job_id>')
@login_required
def download_scan(job_id):
    """Download scan file"""
    job = ScanJob.query.get_or_404(job_id)
    
    if job.user_id != current_user.id and current_user.role != 'admin':
        flash('Access denied', 'error')
        return redirect(url_for('scanning.index'))
    
    if job.status != 'completed' or not job.file_path:
        flash('Scan file not available', 'error')
        return redirect(url_for('scanning.job_status', job_id=job_id))
    
    from flask import send_file
    return send_file(job.file_path, as_attachment=True, download_name=job.filename)

@scanning_bp.route('/api/scanner-status/<int:scanner_id>')
def api_scanner_status(scanner_id):
    """Get real-time scanner status"""
    scanner = Printer.query.get_or_404(scanner_id)
    
    if not scanner.supports_scanning:
        return jsonify({'error': 'Scanner not available'}), 404
    
    # Simulate scanner status
    import random
    status = {
        'id': scanner.id,
        'name': scanner.name,
        'status': random.choice(['Ready', 'Scanning', 'Busy', 'Maintenance']),
        'adf_loaded': random.choice([True, False]),
        'flatbed_ready': True,
        'last_scan': datetime.now().isoformat()
    }
    
    return jsonify(status)

@scanning_bp.route('/templates')
@login_required  
def scan_templates():
    """Predefined scan templates for common workflows"""
    templates = [
        {
            'name': 'Email to Self',
            'description': 'Scan and email to your registered email address',
            'settings': {
                'scan_type': 'pdf',
                'resolution': 300,
                'color_mode': 'color',
                'destination_type': 'email',
                'destination_path': current_user.email
            }
        },
        {
            'name': 'High Quality Archive',
            'description': 'High resolution scan for archival purposes',
            'settings': {
                'scan_type': 'pdf',
                'resolution': 600,
                'color_mode': 'color',
                'destination_type': 'folder',
                'destination_path': '/archive/documents'
            }
        },
        {
            'name': 'Quick B&W Document',
            'description': 'Fast black and white document scan',
            'settings': {
                'scan_type': 'pdf',
                'resolution': 200,
                'color_mode': 'bw',
                'destination_type': 'download'
            }
        }
    ]
    
    return render_template('scanning/templates.html', templates=templates)