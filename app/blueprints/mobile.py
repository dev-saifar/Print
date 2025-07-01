"""
Mobile App Interface Blueprint
Provides responsive mobile interface for print management
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
import os
import uuid

from .. import db
from ..models import PrintJob, Printer, User
from ..utils import allowed_file, get_file_pages

mobile_bp = Blueprint('mobile', __name__, url_prefix='/mobile')

@mobile_bp.route('/')
def index():
    """Mobile app landing page"""
    return render_template('mobile/index.html')

@mobile_bp.route('/dashboard')
@login_required
def dashboard():
    """Mobile dashboard with quick actions"""
    # Get user's recent jobs
    recent_jobs = PrintJob.query.filter_by(user_id=current_user.id)\
                               .order_by(PrintJob.created_at.desc())\
                               .limit(5).all()
    
    # Get nearby printers (simulated based on location)
    nearby_printers = Printer.query.filter_by(is_active=True).limit(3).all()
    
    # User stats
    pending_jobs = PrintJob.query.filter_by(user_id=current_user.id, status='pending').count()
    monthly_usage = current_user.get_monthly_usage()
    
    return render_template('mobile/dashboard.html',
                         recent_jobs=recent_jobs,
                         nearby_printers=nearby_printers,
                         pending_jobs=pending_jobs,
                         monthly_usage=monthly_usage)

@mobile_bp.route('/print')
@login_required
def print_menu():
    """Mobile print options menu"""
    return render_template('mobile/print_menu.html')

@mobile_bp.route('/upload', methods=['GET', 'POST'])
@login_required
def mobile_upload():
    """Mobile file upload interface"""
    if request.method == 'POST':
        if 'file' not in request.files:
            return jsonify({'error': 'No file selected'}), 400
        
        file = request.files['file']
        if file.filename == '' or not file:
            return jsonify({'error': 'No file selected'}), 400
        
        if file and allowed_file(file.filename):
            # Process file upload
            filename = secure_filename(file.filename or "untitled")
            unique_filename = f"{uuid.uuid4()}_{filename}"
            file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], unique_filename)
            file.save(file_path)
            
            # Calculate pages
            total_pages = get_file_pages(file_path)
            
            # Return file info for preview
            return jsonify({
                'success': True,
                'filename': filename,
                'unique_filename': unique_filename,
                'pages': total_pages,
                'file_size': os.path.getsize(file_path)
            })
        else:
            return jsonify({'error': 'Invalid file type'}), 400
    
    return render_template('mobile/upload.html')

@mobile_bp.route('/preview/<filename>')
@login_required
def preview_file(filename):
    """Preview uploaded file before printing"""
    # Get available printers
    printers = Printer.query.filter_by(is_active=True).all()
    
    # Calculate estimated costs for different options
    file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
    if not os.path.exists(file_path):
        flash('File not found', 'error')
        return redirect(url_for('mobile.dashboard'))
    
    pages = get_file_pages(file_path)
    original_filename = filename.split('_', 1)[1] if '_' in filename else filename
    
    return render_template('mobile/preview.html',
                         filename=filename,
                         original_filename=original_filename,
                         pages=pages,
                         printers=printers)

@mobile_bp.route('/submit-job', methods=['POST'])
@login_required
def submit_print_job():
    """Submit print job from mobile"""
    data = request.get_json()
    
    filename = data.get('filename')
    printer_id = data.get('printer_id')
    copies = int(data.get('copies', 1))
    color_mode = data.get('color_mode', 'bw')
    duplex = data.get('duplex', False)
    
    file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
    if not os.path.exists(file_path):
        return jsonify({'error': 'File not found'}), 400
    
    # Create print job
    total_pages = get_file_pages(file_path)
    original_filename = filename.split('_', 1)[1] if '_' in filename else filename
    
    print_job = PrintJob(
        filename=filename,
        original_filename=original_filename,
        file_path=file_path,
        user_id=current_user.id,
        copies=copies,
        color_mode=color_mode,
        duplex=duplex,
        total_pages=total_pages,
        printer_id=printer_id,
        department_id=current_user.department_id
    )
    
    print_job.calculate_cost()
    
    # Check user quota and balance
    if not current_user.can_print(total_pages * copies, print_job.total_cost):
        return jsonify({'error': 'Insufficient balance or quota exceeded'}), 400
    
    db.session.add(print_job)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'job_id': print_job.id,
        'cost': print_job.total_cost,
        'message': 'Print job submitted successfully'
    })

@mobile_bp.route('/jobs')
@login_required
def mobile_jobs():
    """Mobile jobs list with swipe actions"""
    status_filter = request.args.get('status', 'all')
    
    query = PrintJob.query.filter_by(user_id=current_user.id)
    if status_filter != 'all':
        query = query.filter_by(status=status_filter)
    
    jobs = query.order_by(PrintJob.created_at.desc()).limit(20).all()
    
    return render_template('mobile/jobs.html', jobs=jobs, status_filter=status_filter)

@mobile_bp.route('/jobs/<int:job_id>')
@login_required
def job_detail(job_id):
    """Mobile job detail view"""
    job = PrintJob.query.get_or_404(job_id)
    
    if job.user_id != current_user.id and current_user.role != 'admin':
        flash('Access denied', 'error')
        return redirect(url_for('mobile.mobile_jobs'))
    
    return render_template('mobile/job_detail.html', job=job)

@mobile_bp.route('/printer-finder')
@login_required
def printer_finder():
    """Find nearby printers with location services"""
    # Simulate location-based printer discovery
    printers = Printer.query.filter_by(is_active=True).all()
    
    # Add simulated distance and status
    for printer in printers:
        import random
        printer.distance = round(random.uniform(10, 500), 1)  # meters
        printer.queue_length = random.randint(0, 5)
        printer.estimated_wait = printer.queue_length * 2  # minutes
    
    # Sort by distance
    printers.sort(key=lambda p: p.distance)
    
    return render_template('mobile/printer_finder.html', printers=printers)

@mobile_bp.route('/printer/<int:printer_id>/info')
@login_required
def printer_info(printer_id):
    """Detailed printer information"""
    printer = Printer.query.get_or_404(printer_id)
    
    # Get current queue for this printer
    queue_jobs = PrintJob.query.filter_by(printer_id=printer_id, status='printing').count()
    pending_jobs = PrintJob.query.filter_by(printer_id=printer_id, status='pending').count()
    
    # Simulate real-time status
    import random
    status_info = {
        'status': random.choice(['Ready', 'Printing', 'Busy']),
        'toner_level': random.randint(20, 100),
        'paper_level': random.randint(30, 100),
        'queue_length': queue_jobs,
        'pending_count': pending_jobs,
        'estimated_wait': queue_jobs * 3  # minutes
    }
    
    return render_template('mobile/printer_info.html', 
                         printer=printer, 
                         status=status_info)

@mobile_bp.route('/scan')
@login_required
def mobile_scan():
    """Mobile scanning interface"""
    # Get scanners (printers with scan capability)
    scanners = Printer.query.filter_by(supports_scanning=True, is_active=True).all()
    
    return render_template('mobile/scan.html', scanners=scanners)

@mobile_bp.route('/scan/<int:scanner_id>')
@login_required
def scanner_interface(scanner_id):
    """Mobile scanner control interface"""
    scanner = Printer.query.get_or_404(scanner_id)
    
    if not scanner.supports_scanning:
        flash('This device does not support scanning', 'error')
        return redirect(url_for('mobile.mobile_scan'))
    
    return render_template('mobile/scanner.html', scanner=scanner)

@mobile_bp.route('/account')
@login_required
def account():
    """Mobile account management"""
    # Get usage statistics
    monthly_usage = current_user.get_monthly_usage()
    recent_activity = PrintJob.query.filter_by(user_id=current_user.id)\
                                   .order_by(PrintJob.created_at.desc())\
                                   .limit(10).all()
    
    return render_template('mobile/account.html',
                         user=current_user,
                         monthly_usage=monthly_usage,
                         recent_activity=recent_activity)

@mobile_bp.route('/notifications')
@login_required
def notifications():
    """Mobile notifications center"""
    # Simulate notifications based on job status and system events
    notifications = []
    
    # Check for completed jobs
    completed_jobs = PrintJob.query.filter_by(
        user_id=current_user.id, 
        status='completed'
    ).filter(PrintJob.completed_at >= datetime.now() - timedelta(hours=24)).all()
    
    for job in completed_jobs:
        notifications.append({
            'type': 'success',
            'title': 'Print Job Completed',
            'message': f'"{job.original_filename}" has been printed successfully',
            'timestamp': job.completed_at,
            'icon': 'check-circle'
        })
    
    # Check for failed jobs
    failed_jobs = PrintJob.query.filter_by(
        user_id=current_user.id, 
        status='failed'
    ).filter(PrintJob.created_at >= datetime.now() - timedelta(hours=24)).all()
    
    for job in failed_jobs:
        notifications.append({
            'type': 'error',
            'title': 'Print Job Failed',
            'message': f'"{job.original_filename}" failed to print: {job.notes}',
            'timestamp': job.created_at,
            'icon': 'x-circle'
        })
    
    # Check quota warnings
    if current_user.quota_used / current_user.quota_limit > 0.8:
        notifications.append({
            'type': 'warning',
            'title': 'Quota Warning',
            'message': f'You have used {current_user.quota_used}/{current_user.quota_limit} pages this month',
            'timestamp': datetime.now(),
            'icon': 'alert-triangle'
        })
    
    # Sort by timestamp
    notifications.sort(key=lambda n: n['timestamp'], reverse=True)
    
    return render_template('mobile/notifications.html', notifications=notifications)

@mobile_bp.route('/help')
def help():
    """Mobile help and support"""
    return render_template('mobile/help.html')

@mobile_bp.route('/api/printer-status/<int:printer_id>')
def api_printer_status(printer_id):
    """API endpoint for real-time printer status"""
    printer = Printer.query.get_or_404(printer_id)
    
    # Simulate real-time status
    import random
    status = {
        'id': printer.id,
        'name': printer.name,
        'status': random.choice(['Ready', 'Printing', 'Busy', 'Offline']),
        'toner_level': random.randint(0, 100),
        'paper_level': random.randint(0, 100),
        'queue_length': PrintJob.query.filter_by(printer_id=printer_id, status='printing').count(),
        'last_updated': datetime.now().isoformat()
    }
    
    return jsonify(status)

@mobile_bp.route('/api/quick-print', methods=['POST'])
@login_required
def api_quick_print():
    """API for quick print from mobile photo/document"""
    # Handle file upload from mobile camera or gallery
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    if not file or file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    # Quick print with default settings
    filename = secure_filename(file.filename or "mobile_capture")
    unique_filename = f"mobile_{uuid.uuid4()}_{filename}"
    file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], unique_filename)
    file.save(file_path)
    
    # Create print job with default settings
    print_job = PrintJob(
        filename=unique_filename,
        original_filename=filename,
        file_path=file_path,
        user_id=current_user.id,
        copies=1,
        color_mode='bw',
        duplex=False,
        total_pages=1,  # Assume single page for quick print
        department_id=current_user.department_id
    )
    
    print_job.calculate_cost()
    
    if not current_user.can_print(1, print_job.total_cost):
        return jsonify({'error': 'Insufficient balance or quota'}), 400
    
    db.session.add(print_job)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'job_id': print_job.id,
        'message': 'Quick print job created. Visit a printer to release.'
    })