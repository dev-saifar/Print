from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file, abort, current_app
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
import os
import uuid
from datetime import datetime, timedelta
from sqlalchemy import func, desc
import PyPDF2
import io

from . import db, scheduler
from .models import User, PrintJob, Department, SystemSettings, Printer, PrintPolicy
from .utils import allowed_file, get_file_pages, process_print_job

# Create Blueprint
bp = Blueprint('main', __name__)

@bp.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    return render_template('index.html')

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = User.query.filter_by(username=username).first()
        
        if user and user.is_active and check_password_hash(user.password_hash, password):
            login_user(user)
            next_page = request.args.get('next')
            flash(f'Welcome back, {user.username}!', 'success')
            return redirect(next_page) if next_page else redirect(url_for('main.dashboard'))
        else:
            flash('Invalid username or password', 'error')
    
    return render_template('login.html')

@bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        
        # Validation
        if password != confirm_password:
            flash('Passwords do not match', 'error')
            return render_template('register.html')
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists', 'error')
            return render_template('register.html')
        
        if User.query.filter_by(email=email).first():
            flash('Email already registered', 'error')
            return render_template('register.html')
        
        # Create new user
        user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password),
            balance=10.0,  # Starting balance
            quota_limit=500  # Starting quota
        )
        
        db.session.add(user)
        db.session.commit()
        
        flash('Registration successful! You can now log in.', 'success')
        return redirect(url_for('main.login'))
    
    return render_template('register.html')

@bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out', 'info')
    return redirect(url_for('main.index'))

@bp.route('/dashboard')
@login_required
def dashboard():
    # Get user statistics
    total_jobs = PrintJob.query.filter_by(user_id=current_user.id).count()
    completed_jobs = PrintJob.query.filter_by(user_id=current_user.id, status='completed').count()
    pending_jobs = PrintJob.query.filter_by(user_id=current_user.id, status='pending').count()
    
    # Recent jobs
    recent_jobs = PrintJob.query.filter_by(user_id=current_user.id).order_by(desc(PrintJob.created_at)).limit(5).all()
    
    # Monthly usage
    monthly_usage = current_user.get_monthly_usage()
    
    # Total spent this month
    current_month = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    monthly_cost = db.session.query(func.sum(PrintJob.total_cost)).filter(
        PrintJob.user_id == current_user.id,
        PrintJob.created_at >= current_month,
        PrintJob.status == 'completed'
    ).scalar() or 0
    
    return render_template('dashboard.html', 
                         total_jobs=total_jobs,
                         completed_jobs=completed_jobs,
                         pending_jobs=pending_jobs,
                         recent_jobs=recent_jobs,
                         monthly_usage=monthly_usage,
                         monthly_cost=monthly_cost)

@bp.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file selected', 'error')
            return redirect(request.url)
        
        file = request.files['file']
        if file.filename == '':
            flash('No file selected', 'error')
            return redirect(request.url)
        
        if file and allowed_file(file.filename):
            # Get form data
            copies = int(request.form.get('copies', 1))
            color_mode = request.form.get('color_mode', 'bw')
            duplex = 'duplex' in request.form
            paper_size = request.form.get('paper_size', 'A4')
            priority = request.form.get('priority', 'normal')
            notes = request.form.get('notes', '')
            
            # Save file
            filename = str(uuid.uuid4()) + '_' + secure_filename(file.filename)
            file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            
            # Get page count
            pages = get_file_pages(file_path)
            
            # Create print job
            print_job = PrintJob(
                filename=filename,
                original_filename=file.filename,
                file_path=file_path,
                user_id=current_user.id,
                copies=copies,
                color_mode=color_mode,
                duplex=duplex,
                paper_size=paper_size,
                priority=priority,
                notes=notes,
                total_pages=pages
            )
            
            # Calculate cost
            print_job.calculate_cost()
            
            # Check if user can afford and has quota
            if not current_user.can_print(pages * copies, print_job.total_cost):
                os.remove(file_path)  # Clean up file
                flash('Insufficient balance or quota exceeded', 'error')
                return redirect(request.url)
            
            db.session.add(print_job)
            db.session.commit()
            
            # Schedule print job processing
            scheduler.add_job(
                func=process_print_job,
                args=[print_job.id],
                trigger='date',
                run_date=datetime.utcnow() + timedelta(seconds=5),
                id=f'print_job_{print_job.id}'
            )
            
            flash(f'Print job submitted successfully! Cost: ${print_job.total_cost:.2f}', 'success')
            return redirect(url_for('main.jobs'))
        else:
            flash('Invalid file type. Please upload PDF, DOC, DOCX, or image files.', 'error')
    
    return render_template('upload.html')

@bp.route('/jobs')
@login_required
def jobs():
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', 'all')
    
    query = PrintJob.query.filter_by(user_id=current_user.id)
    
    if status_filter != 'all':
        query = query.filter_by(status=status_filter)
    
    jobs = query.order_by(desc(PrintJob.created_at)).paginate(
        page=page, per_page=10, error_out=False
    )
    
    return render_template('jobs.html', jobs=jobs, status_filter=status_filter)

@bp.route('/job/<int:job_id>/cancel', methods=['POST'])
@login_required
def cancel_job(job_id):
    job = PrintJob.query.get_or_404(job_id)
    
    if job.user_id != current_user.id and current_user.role != 'admin':
        abort(403)
    
    if job.status == 'pending':
        job.status = 'cancelled'
        db.session.commit()
        flash('Print job cancelled successfully', 'success')
    else:
        flash('Cannot cancel job that is already processing or completed', 'error')
    
    return redirect(url_for('main.jobs'))

@bp.route('/admin')
@login_required
def admin():
    if current_user.role != 'admin':
        abort(403)
    
    # System statistics
    total_users = User.query.count()
    active_users = User.query.filter_by(is_active=True).count()
    total_jobs = PrintJob.query.count()
    pending_jobs = PrintJob.query.filter_by(status='pending').count()
    
    # Recent activity
    recent_jobs = PrintJob.query.order_by(desc(PrintJob.created_at)).limit(10).all()
    recent_users = User.query.order_by(desc(User.created_at)).limit(5).all()
    
    return render_template('admin.html',
                         total_users=total_users,
                         active_users=active_users,
                         total_jobs=total_jobs,
                         pending_jobs=pending_jobs,
                         recent_jobs=recent_jobs,
                         recent_users=recent_users)

@bp.route('/admin/users')
@login_required
def admin_users():
    if current_user.role != 'admin':
        abort(403)
    
    page = request.args.get('page', 1, type=int)
    users = User.query.order_by(User.username).paginate(
        page=page, per_page=20, error_out=False
    )
    
    return render_template('admin_users.html', users=users)

@bp.route('/admin/user/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
def admin_edit_user(user_id):
    if current_user.role != 'admin':
        abort(403)
    
    user = User.query.get_or_404(user_id)
    
    if request.method == 'POST':
        user.balance = float(request.form.get('balance', user.balance))
        user.quota_limit = int(request.form.get('quota_limit', user.quota_limit))
        user.role = request.form.get('role', user.role)
        user.is_active = 'is_active' in request.form
        
        db.session.commit()
        flash(f'User {user.username} updated successfully', 'success')
        return redirect(url_for('main.admin_users'))
    
    return render_template('admin_edit_user.html', user=user)

@bp.route('/reports')
@login_required
def reports():
    # Date range filter
    days = request.args.get('days', 30, type=int)
    start_date = datetime.utcnow() - timedelta(days=days)
    
    if current_user.role == 'admin':
        # Admin sees all data
        jobs_query = PrintJob.query.filter(PrintJob.created_at >= start_date)
        users_data = User.query.all()
    else:
        # Regular users see only their data
        jobs_query = PrintJob.query.filter(
            PrintJob.user_id == current_user.id,
            PrintJob.created_at >= start_date
        )
        users_data = [current_user]
    
    # Statistics
    total_jobs = jobs_query.count()
    completed_jobs = jobs_query.filter_by(status='completed').count()
    total_pages = db.session.query(func.sum(PrintJob.total_pages)).filter(
        PrintJob.created_at >= start_date,
        PrintJob.status == 'completed'
    ).scalar() or 0
    total_cost = db.session.query(func.sum(PrintJob.total_cost)).filter(
        PrintJob.created_at >= start_date,
        PrintJob.status == 'completed'
    ).scalar() or 0
    
    # Daily usage data for charts
    daily_stats = db.session.query(
        func.date(PrintJob.created_at).label('date'),
        func.count(PrintJob.id).label('jobs'),
        func.sum(PrintJob.total_pages).label('pages'),
        func.sum(PrintJob.total_cost).label('cost')
    ).filter(
        PrintJob.created_at >= start_date,
        PrintJob.status == 'completed'
    ).group_by(func.date(PrintJob.created_at)).all()
    
    return render_template('reports.html',
                         total_jobs=total_jobs,
                         completed_jobs=completed_jobs,
                         total_pages=total_pages,
                         total_cost=total_cost,
                         daily_stats=daily_stats,
                         days=days)

@bp.route('/api/chart_data')
@login_required
def chart_data():
    days = request.args.get('days', 30, type=int)
    start_date = datetime.utcnow() - timedelta(days=days)
    
    if current_user.role == 'admin':
        jobs_query = PrintJob.query.filter(PrintJob.created_at >= start_date, PrintJob.status == 'completed')
    else:
        jobs_query = PrintJob.query.filter(
            PrintJob.user_id == current_user.id,
            PrintJob.created_at >= start_date,
            PrintJob.status == 'completed'
        )
    
    # Daily statistics
    daily_stats = db.session.query(
        func.date(PrintJob.created_at).label('date'),
        func.count(PrintJob.id).label('jobs'),
        func.sum(PrintJob.total_pages).label('pages'),
        func.sum(PrintJob.total_cost).label('cost')
    ).filter(
        PrintJob.created_at >= start_date,
        PrintJob.status == 'completed'
    ).group_by(func.date(PrintJob.created_at)).all()
    
    # Color vs BW breakdown
    color_stats = db.session.query(
        PrintJob.color_mode,
        func.count(PrintJob.id).label('count'),
        func.sum(PrintJob.total_pages).label('pages')
    ).filter(
        PrintJob.created_at >= start_date,
        PrintJob.status == 'completed'
    ).group_by(PrintJob.color_mode).all()
    
    return jsonify({
        'daily': [{
            'date': stat.date.strftime('%Y-%m-%d'),
            'jobs': stat.jobs or 0,
            'pages': stat.pages or 0,
            'cost': float(stat.cost or 0)
        } for stat in daily_stats],
        'color_breakdown': [{
            'mode': stat.color_mode,
            'count': stat.count,
            'pages': stat.pages or 0
        } for stat in color_stats]
    })

# Printer Management Routes
@bp.route('/admin/printers')
@login_required
def admin_printers():
    if current_user.role != 'admin':
        abort(403)
    
    page = request.args.get('page', 1, type=int)
    printers = Printer.query.order_by(Printer.name).paginate(
        page=page, per_page=20, error_out=False
    )
    
    return render_template('admin_printers.html', printers=printers)

@bp.route('/admin/printer/add', methods=['GET', 'POST'])
@login_required
def admin_add_printer():
    if current_user.role != 'admin':
        abort(403)
    
    if request.method == 'POST':
        printer = Printer(
            name=request.form['name'],
            model=request.form.get('model', ''),
            location=request.form.get('location', ''),
            ip_address=request.form.get('ip_address', ''),
            port=int(request.form.get('port', 9100)),
            supports_color='supports_color' in request.form,
            supports_duplex='supports_duplex' in request.form,
            supports_scanning='supports_scanning' in request.form,
            max_paper_size=request.form.get('max_paper_size', 'A4'),
            status=request.form.get('status', 'offline'),
            toner_level=int(request.form.get('toner_level', 100)),
            paper_level=int(request.form.get('paper_level', 100)),
            is_default='is_default' in request.form,
            is_active='is_active' in request.form
        )
        
        # Ensure only one default printer
        if printer.is_default:
            Printer.query.filter_by(is_default=True).update({'is_default': False})
        
        db.session.add(printer)
        db.session.commit()
        
        flash(f'Printer {printer.name} added successfully!', 'success')
        return redirect(url_for('main.admin_printers'))
    
    return render_template('admin_add_printer.html')

@bp.route('/admin/printer/<int:printer_id>/edit', methods=['GET', 'POST'])
@login_required
def admin_edit_printer(printer_id):
    if current_user.role != 'admin':
        abort(403)
    
    printer = Printer.query.get_or_404(printer_id)
    
    if request.method == 'POST':
        printer.name = request.form['name']
        printer.model = request.form.get('model', '')
        printer.location = request.form.get('location', '')
        printer.ip_address = request.form.get('ip_address', '')
        printer.port = int(request.form.get('port', 9100))
        printer.supports_color = 'supports_color' in request.form
        printer.supports_duplex = 'supports_duplex' in request.form
        printer.supports_scanning = 'supports_scanning' in request.form
        printer.max_paper_size = request.form.get('max_paper_size', 'A4')
        printer.status = request.form.get('status', 'offline')
        printer.toner_level = int(request.form.get('toner_level', 100))
        printer.paper_level = int(request.form.get('paper_level', 100))
        printer.is_active = 'is_active' in request.form
        
        # Handle default printer
        if 'is_default' in request.form and not printer.is_default:
            Printer.query.filter_by(is_default=True).update({'is_default': False})
            printer.is_default = True
        elif 'is_default' not in request.form:
            printer.is_default = False
        
        db.session.commit()
        flash(f'Printer {printer.name} updated successfully!', 'success')
        return redirect(url_for('main.admin_printers'))
    
    return render_template('admin_edit_printer.html', printer=printer)

@bp.route('/admin/printer/<int:printer_id>/delete', methods=['POST'])
@login_required
def admin_delete_printer(printer_id):
    if current_user.role != 'admin':
        abort(403)
    
    printer = Printer.query.get_or_404(printer_id)
    
    # Check if printer has print jobs
    if printer.print_jobs:
        flash('Cannot delete printer with existing print jobs', 'error')
        return redirect(url_for('main.admin_printers'))
    
    db.session.delete(printer)
    db.session.commit()
    
    flash(f'Printer {printer.name} deleted successfully!', 'success')
    return redirect(url_for('main.admin_printers'))

# Print Policies Management
@bp.route('/admin/policies')
@login_required
def admin_policies():
    if current_user.role != 'admin':
        abort(403)
    
    policies = PrintPolicy.query.order_by(PrintPolicy.name).all()
    return render_template('admin_policies.html', policies=policies)

@bp.route('/admin/policy/add', methods=['GET', 'POST'])
@login_required
def admin_add_policy():
    if current_user.role != 'admin':
        abort(403)
    
    if request.method == 'POST':
        policy = PrintPolicy(
            name=request.form['name'],
            description=request.form.get('description', ''),
            force_duplex_over_pages=int(request.form.get('force_duplex_over_pages', 0)),
            force_bw_over_pages=int(request.form.get('force_bw_over_pages', 0)),
            max_pages_per_job=int(request.form.get('max_pages_per_job', 0)),
            max_copies=int(request.form.get('max_copies', 10)),
            color_cost_multiplier=float(request.form.get('color_cost_multiplier', 1.0)),
            bw_cost_multiplier=float(request.form.get('bw_cost_multiplier', 1.0)),
            user_role=request.form.get('user_role') if request.form.get('user_role') else None,
            is_active='is_active' in request.form
        )
        
        db.session.add(policy)
        db.session.commit()
        
        flash(f'Print policy {policy.name} created successfully!', 'success')
        return redirect(url_for('main.admin_policies'))
    
    return render_template('admin_add_policy.html')

# Scanning Routes
@bp.route('/scan')
@login_required
def scan_documents():
    # Get available scanners (printers with scanning capability)
    scanners = Printer.query.filter_by(supports_scanning=True, is_active=True).all()
    return render_template('scan.html', scanners=scanners)

@bp.route('/scan/start', methods=['POST'])
@login_required
def start_scan():
    scanner_id = request.form.get('scanner_id')
    scanner = Printer.query.get_or_404(scanner_id)
    
    if not scanner.supports_scanning:
        flash('Selected device does not support scanning', 'error')
        return redirect(url_for('main.scan_documents'))
    
    # Simulate scan job creation
    scan_settings = {
        'resolution': request.form.get('resolution', 300),
        'color_mode': request.form.get('color_mode', 'color'),
        'output_format': request.form.get('output_format', 'pdf'),
        'ocr_enabled': 'ocr_enabled' in request.form,
        'destination_type': request.form.get('destination_type', 'download'),
        'document_type': request.form.get('document_type', ''),
        'notes': request.form.get('notes', '')
    }
    
    # For demo purposes, simulate successful scan
    flash('Scan job started successfully! Document will be processed shortly.', 'success')
    return redirect(url_for('main.scan_documents'))

# Mobile App Simulation Routes
@bp.route('/mobile')
def mobile_app():
    """Mobile app interface simulation"""
    return render_template('mobile_app.html')

@bp.route('/mobile/print', methods=['POST'])
def mobile_print():
    """Handle mobile print requests"""
    # Simulate mobile print job
    device_info = request.headers.get('User-Agent', 'Unknown Device')
    
    # For demo purposes
    flash('Print job sent from mobile device successfully!', 'success')
    return jsonify({'status': 'success', 'message': 'Print job queued'})

# Email-to-Print Simulation
@bp.route('/admin/email-to-print')
@login_required
def admin_email_to_print():
    if current_user.role != 'admin':
        abort(403)
    
    return render_template('admin_email_to_print.html')

# User management helper routes
@bp.route('/admin/user/add', methods=['POST'])
@login_required
def admin_add_user():
    if current_user.role != 'admin':
        abort(403)
    
    username = request.form['username']
    email = request.form['email']
    password = request.form['password']
    role = request.form['role']
    balance = float(request.form.get('balance', 10.0))
    quota_limit = int(request.form.get('quota_limit', 500))
    
    # Check if user exists
    if User.query.filter_by(username=username).first():
        flash('Username already exists', 'error')
        return redirect(url_for('main.admin_users'))
    
    if User.query.filter_by(email=email).first():
        flash('Email already registered', 'error')
        return redirect(url_for('main.admin_users'))
    
    user = User(
        username=username,
        email=email,
        password_hash=generate_password_hash(password),
        role=role,
        balance=balance,
        quota_limit=quota_limit
    )
    
    db.session.add(user)
    db.session.commit()
    
    flash(f'User {username} created successfully!', 'success')
    return redirect(url_for('main.admin_users'))

@bp.route('/admin/user/<int:user_id>/toggle-status', methods=['POST'])
@login_required
def admin_toggle_user_status(user_id):
    if current_user.role != 'admin':
        abort(403)
    
    user = User.query.get_or_404(user_id)
    user.is_active = not user.is_active
    db.session.commit()
    
    status = 'activated' if user.is_active else 'deactivated'
    return jsonify({'success': True, 'message': f'User {status} successfully'})

@bp.route('/admin/user/<int:user_id>/reset-quota', methods=['POST'])
@login_required
def admin_reset_user_quota(user_id):
    if current_user.role != 'admin':
        abort(403)
    
    user = User.query.get_or_404(user_id)
    user.quota_used = 0
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Quota reset successfully'})

@bp.route('/admin/user/<int:user_id>/reset-password', methods=['POST'])
@login_required  
def admin_reset_user_password(user_id):
    if current_user.role != 'admin':
        abort(403)
    
    user = User.query.get_or_404(user_id)
    
    # Generate temporary password
    import string
    import random
    temp_password = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
    
    user.password_hash = generate_password_hash(temp_password)
    db.session.commit()
    
    return jsonify({'success': True, 'password': temp_password})
