"""
Printer Panel Blueprint
Handles embedded printer panel authentication and job release
Simulates physical printer touchscreen interface
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from werkzeug.security import check_password_hash
from datetime import datetime
import qrcode
import io
import base64

from .. import db
from ..models import User, PrintJob, Printer
from ..utils import process_print_job

panel_bp = Blueprint('panel', __name__, url_prefix='/panel')

@panel_bp.route('/')
def index():
    """Main printer panel interface"""
    printer_id = request.args.get('printer_id', 1)
    printer = Printer.query.get_or_404(printer_id)
    return render_template('panel/index.html', printer=printer)

@panel_bp.route('/auth', methods=['GET', 'POST'])
def authenticate():
    """Authentication interface for printer panel"""
    printer_id = request.args.get('printer_id', 1)
    printer = Printer.query.get_or_404(printer_id)
    
    if request.method == 'POST':
        auth_method = request.form.get('auth_method')
        
        if auth_method == 'pin':
            username = request.form.get('username')
            pin = request.form.get('pin')
            
            user = User.query.filter_by(username=username, is_active=True).first()
            if user and check_password_hash(user.password_hash, pin):
                return redirect(url_for('panel.jobs', 
                                      printer_id=printer_id, 
                                      user_id=user.id))
            else:
                flash('Invalid username or PIN', 'error')
        
        elif auth_method == 'card':
            card_id = request.form.get('card_id')
            # Simulate card authentication
            # In real implementation, this would check against card database
            user = User.query.filter_by(username=card_id, is_active=True).first()
            if user:
                return redirect(url_for('panel.jobs', 
                                      printer_id=printer_id, 
                                      user_id=user.id))
            else:
                flash('Card not recognized', 'error')
        
        elif auth_method == 'print_code':
            print_code = request.form.get('print_code')
            # Find jobs with matching print code
            jobs = PrintJob.query.filter_by(print_code=print_code, status='pending').all()
            if jobs:
                user = jobs[0].user
                return redirect(url_for('panel.jobs', 
                                      printer_id=printer_id, 
                                      user_id=user.id,
                                      print_code=print_code))
            else:
                flash('Invalid print code', 'error')
    
    return render_template('panel/auth.html', printer=printer)

@panel_bp.route('/jobs')
def jobs():
    """Display pending jobs for authenticated user"""
    printer_id = request.args.get('printer_id', 1)
    user_id = request.args.get('user_id')
    print_code = request.args.get('print_code')
    
    if not user_id:
        return redirect(url_for('panel.authenticate', printer_id=printer_id))
    
    printer = Printer.query.get_or_404(printer_id)
    user = User.query.get_or_404(user_id)
    
    # Get pending jobs for user
    query = PrintJob.query.filter_by(user_id=user_id, status='pending')
    
    # If print code provided, filter by it
    if print_code:
        query = query.filter_by(print_code=print_code)
    
    pending_jobs = query.all()
    
    return render_template('panel/jobs.html', 
                         printer=printer, 
                         user=user, 
                         jobs=pending_jobs,
                         print_code=print_code)

@panel_bp.route('/release/<int:job_id>')
def release_job(job_id):
    """Release specific job for printing"""
    printer_id = request.args.get('printer_id', 1)
    job = PrintJob.query.get_or_404(job_id)
    printer = Printer.query.get_or_404(printer_id)
    
    if job.status != 'pending':
        flash('Job is not available for release', 'error')
        return redirect(url_for('panel.jobs', 
                              printer_id=printer_id, 
                              user_id=job.user_id))
    
    # Update job for printing
    job.status = 'printing'
    job.started_at = datetime.utcnow()
    job.printer_id = printer_id
    job.printer_name = printer.name
    
    # Deduct cost and quota
    user = job.user
    user.balance -= job.total_cost
    user.quota_used += (job.total_pages * job.copies)
    
    db.session.commit()
    
    # Start printing simulation
    from ..utils import process_print_job
    process_print_job(job.id)
    
    flash(f'Print job "{job.original_filename}" released for printing', 'success')
    return render_template('panel/printing.html', job=job, printer=printer)

@panel_bp.route('/release-all')
def release_all():
    """Release all pending jobs for user"""
    printer_id = request.args.get('printer_id', 1)
    user_id = request.args.get('user_id')
    print_code = request.args.get('print_code')
    
    if not user_id:
        return redirect(url_for('panel.authenticate', printer_id=printer_id))
    
    printer = Printer.query.get_or_404(printer_id)
    user = User.query.get_or_404(user_id)
    
    # Get pending jobs
    query = PrintJob.query.filter_by(user_id=user_id, status='pending')
    if print_code:
        query = query.filter_by(print_code=print_code)
    
    jobs = query.all()
    
    total_cost = 0
    total_pages = 0
    
    for job in jobs:
        job.status = 'printing'
        job.started_at = datetime.utcnow()
        job.printer_id = printer_id
        job.printer_name = printer.name
        
        total_cost += job.total_cost
        total_pages += (job.total_pages * job.copies)
        
        # Start printing simulation
        from ..utils import process_print_job
        process_print_job(job.id)
    
    # Deduct total cost and quota
    user.balance -= total_cost
    user.quota_used += total_pages
    
    db.session.commit()
    
    flash(f'Released {len(jobs)} print jobs', 'success')
    return render_template('panel/printing_multiple.html', 
                         jobs=jobs, 
                         printer=printer,
                         total_cost=total_cost)

@panel_bp.route('/scan')
def scan_interface():
    """Scanning interface for MFP devices"""
    printer_id = request.args.get('printer_id', 1)
    user_id = request.args.get('user_id')
    
    printer = Printer.query.get_or_404(printer_id)
    
    if not printer.supports_scanning:
        flash('This printer does not support scanning', 'error')
        return redirect(url_for('panel.index', printer_id=printer_id))
    
    user = None
    if user_id:
        user = User.query.get(user_id)
    
    return render_template('panel/scan.html', printer=printer, user=user)

@panel_bp.route('/scan/start', methods=['POST'])
def start_scan():
    """Start scanning process"""
    printer_id = request.args.get('printer_id', 1)
    user_id = request.form.get('user_id')
    
    # Scan settings
    scan_type = request.form.get('scan_type', 'pdf')  # pdf, jpeg, png
    resolution = int(request.form.get('resolution', 300))  # DPI
    color_mode = request.form.get('color_mode', 'color')  # color, grayscale, bw
    duplex = request.form.get('duplex') == 'on'
    
    # Destination settings
    destination = request.form.get('destination', 'download')  # download, email, folder
    email = request.form.get('email', '')
    folder_path = request.form.get('folder_path', '')
    
    printer = Printer.query.get_or_404(printer_id)
    user = User.query.get(user_id) if user_id else None
    
    # Simulate scanning process
    scan_filename = f"scan_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{scan_type}"
    
    # In real implementation, this would interface with scanner hardware
    scan_data = {
        'filename': scan_filename,
        'type': scan_type,
        'resolution': resolution,
        'color_mode': color_mode,
        'duplex': duplex,
        'destination': destination,
        'email': email,
        'folder_path': folder_path,
        'user': user.username if user else 'Guest',
        'printer': printer.name,
        'timestamp': datetime.now()
    }
    
    # Process scan based on destination
    if destination == 'email' and email:
        # Send scan via email (simulation)
        flash(f'Scan sent to {email}', 'success')
    elif destination == 'folder' and folder_path:
        # Save to network folder (simulation)
        flash(f'Scan saved to {folder_path}', 'success')
    else:
        # Provide download link (simulation)
        flash(f'Scan completed: {scan_filename}', 'success')
    
    return render_template('panel/scan_complete.html', 
                         scan_data=scan_data, 
                         printer=printer)

@panel_bp.route('/status')
def printer_status():
    """Display printer status and supplies"""
    printer_id = request.args.get('printer_id', 1)
    printer = Printer.query.get_or_404(printer_id)
    
    # Simulate real-time printer status
    import random
    status_data = {
        'status': random.choice(['Ready', 'Printing', 'Warming Up']),
        'toner_level': random.randint(10, 100),
        'paper_level': random.randint(20, 100),
        'paper_jams': random.randint(0, 2),
        'pages_printed_today': random.randint(50, 500),
        'queue_length': PrintJob.query.filter_by(printer_id=printer_id, status='printing').count()
    }
    
    return render_template('panel/status.html', 
                         printer=printer, 
                         status=status_data)

@panel_bp.route('/logout')
def logout():
    """Logout from printer panel"""
    printer_id = request.args.get('printer_id', 1)
    flash('Logged out successfully', 'info')
    return redirect(url_for('panel.index', printer_id=printer_id))

@panel_bp.route('/api/generate-qr/<int:user_id>')
def generate_qr_code(user_id):
    """Generate QR code for mobile app access"""
    user = User.query.get_or_404(user_id)
    
    # Create QR code data
    qr_data = f"biztra://print-release?user={user.username}&code={user.id}"
    
    # Generate QR code
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(qr_data)
    qr.make(fit=True)
    
    # Create QR code image
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Convert to base64 for web display
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    img_base64 = base64.b64encode(buffer.getvalue()).decode()
    
    return jsonify({
        'qr_code': f"data:image/png;base64,{img_base64}",
        'data': qr_data
    })

@panel_bp.route('/help')
def help_interface():
    """Help and instructions for printer panel"""
    printer_id = request.args.get('printer_id', 1)
    printer = Printer.query.get_or_404(printer_id)
    
    return render_template('panel/help.html', printer=printer)