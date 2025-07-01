"""
Admin Management Blueprint
Handles user management, system settings, and administrative functions
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta
from sqlalchemy import func, desc

from .. import db
from ..models import (
    User,
    PrintJob,
    Department,
    SystemSettings,
    Printer,
    PrintPolicy,
    PrintQueue,
)
from ..utils import calculate_environmental_impact

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

def admin_required(f):
    """Decorator to require admin role"""
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash('Admin access required', 'error')
            return redirect(url_for('main.dashboard'))
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

@admin_bp.route('/')
@login_required
@admin_required
def dashboard():
    """Admin dashboard with system overview"""
    # Get system statistics
    total_users = User.query.count()
    total_jobs = PrintJob.query.count()
    total_pages = db.session.query(func.sum(PrintJob.total_pages * PrintJob.copies)).scalar() or 0
    
    # Recent activity
    recent_jobs = PrintJob.query.order_by(desc(PrintJob.created_at)).limit(10).all()
    
    # Usage by department
    dept_usage = db.session.query(
        Department.name,
        func.sum(PrintJob.total_pages * PrintJob.copies).label('pages'),
        func.sum(PrintJob.total_cost).label('cost')
    ).join(User).join(PrintJob).group_by(Department.name).all()
    
    # Environmental impact
    env_impact = calculate_environmental_impact(total_pages)
    
    return render_template('admin/dashboard.html',
                         total_users=total_users,
                         total_jobs=total_jobs,
                         total_pages=total_pages,
                         recent_jobs=recent_jobs,
                         dept_usage=dept_usage,
                         env_impact=env_impact)

@admin_bp.route('/users')
@login_required
@admin_required
def users():
    """User management interface"""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    
    query = User.query
    if search:
        query = query.filter(User.username.contains(search) | 
                           User.email.contains(search))
    
    users = query.paginate(page=page, per_page=20, error_out=False)
    departments = Department.query.all()
    
    return render_template('admin/users.html', users=users, departments=departments, search=search)

@admin_bp.route('/users/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_user():
    """Add new user"""
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        role = request.form.get('role', 'user')
        department_id = request.form.get('department_id')
        balance = float(request.form.get('balance', 0))
        quota_limit = int(request.form.get('quota_limit', 1000))
        
        # Check if user already exists
        if User.query.filter_by(username=username).first():
            flash('Username already exists', 'error')
            return redirect(request.url)
        
        if User.query.filter_by(email=email).first():
            flash('Email already exists', 'error')
            return redirect(request.url)
        
        # Create new user
        user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password),
            role=role,
            department_id=department_id if department_id else None,
            balance=balance,
            quota_limit=quota_limit
        )
        
        db.session.add(user)
        db.session.commit()
        
        flash(f'User {username} created successfully', 'success')
        return redirect(url_for('admin.users'))
    
    departments = Department.query.all()
    return render_template('admin/add_user.html', departments=departments)

@admin_bp.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_user(user_id):
    """Edit user details"""
    user = User.query.get_or_404(user_id)
    
    if request.method == 'POST':
        user.username = request.form['username']
        user.email = request.form['email']
        user.role = request.form.get('role', 'user')
        user.department_id = request.form.get('department_id') or None
        user.balance = float(request.form.get('balance', 0))
        user.quota_limit = int(request.form.get('quota_limit', 1000))
        user.is_active = request.form.get('is_active') == 'on'
        
        # Update password if provided
        if request.form.get('password'):
            user.password_hash = generate_password_hash(request.form['password'])
        
        db.session.commit()
        flash(f'User {user.username} updated successfully', 'success')
        return redirect(url_for('admin.users'))
    
    departments = Department.query.all()
    return render_template('admin/edit_user.html', user=user, departments=departments)

@admin_bp.route('/users/<int:user_id>/reset-quota', methods=['POST'])
@login_required
@admin_required
def reset_user_quota(user_id):
    """Reset user's monthly quota"""
    user = User.query.get_or_404(user_id)
    user.quota_used = 0
    db.session.commit()
    
    flash(f'Quota reset for {user.username}', 'success')
    return redirect(url_for('admin.users'))

@admin_bp.route('/users/<int:user_id>/add-credit', methods=['POST'])
@login_required
@admin_required
def add_user_credit(user_id):
    """Add credit to user account"""
    user = User.query.get_or_404(user_id)
    amount = float(request.form.get('amount', 0))
    
    user.balance += amount
    db.session.commit()
    
    flash(f'Added ${amount:.2f} credit to {user.username}', 'success')
    return redirect(url_for('admin.users'))

@admin_bp.route('/printers')
@login_required
@admin_required
def printers():
    """Printer management interface"""
    printers = Printer.query.all()
    departments = Department.query.all()
    return render_template('admin/printers.html', printers=printers, departments=departments)

@admin_bp.route('/printers/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_printer():
    """Add new printer"""
    if request.method == 'POST':
        name = request.form['name']
        model = request.form.get('model', '')
        location = request.form.get('location', '')
        ip_address = request.form.get('ip_address', '')
        port = int(request.form.get('port', 9100))
        department_id = request.form.get('department_id') or None
        
        # Printer capabilities
        supports_color = request.form.get('supports_color') == 'on'
        supports_duplex = request.form.get('supports_duplex') == 'on'
        supports_scanning = request.form.get('supports_scanning') == 'on'
        max_paper_size = request.form.get('max_paper_size', 'A4')
        
        printer = Printer(
            name=name,
            model=model,
            location=location,
            ip_address=ip_address,
            port=port,
            supports_color=supports_color,
            supports_duplex=supports_duplex,
            supports_scanning=supports_scanning,
            max_paper_size=max_paper_size,
            department_id=department_id
        )
        
        db.session.add(printer)
        db.session.commit()
        
        flash(f'Printer {name} added successfully', 'success')
        return redirect(url_for('admin.printers'))
    
    departments = Department.query.all()
    return render_template('admin/add_printer.html', departments=departments)

@admin_bp.route('/policies')
@login_required
@admin_required
def policies():
    """Print policy management"""
    policies = PrintPolicy.query.all()
    return render_template('admin/policies.html', policies=policies)

@admin_bp.route('/policies/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_policy():
    """Add new print policy"""
    if request.method == 'POST':
        name = request.form['name']
        description = request.form.get('description', '')
        
        # Policy rules
        force_duplex_over_pages = int(request.form.get('force_duplex_over_pages', 0))
        force_bw_over_pages = int(request.form.get('force_bw_over_pages', 0))
        max_pages_per_job = int(request.form.get('max_pages_per_job', 0))
        max_copies = int(request.form.get('max_copies', 10))
        
        # Cost multipliers
        color_cost_multiplier = float(request.form.get('color_cost_multiplier', 1.0))
        bw_cost_multiplier = float(request.form.get('bw_cost_multiplier', 1.0))
        
        policy = PrintPolicy(
            name=name,
            description=description,
            force_duplex_over_pages=force_duplex_over_pages,
            force_bw_over_pages=force_bw_over_pages,
            max_pages_per_job=max_pages_per_job,
            max_copies=max_copies,
            color_cost_multiplier=color_cost_multiplier,
            bw_cost_multiplier=bw_cost_multiplier
        )
        
        db.session.add(policy)
        db.session.commit()
        
        flash(f'Policy {name} created successfully', 'success')
        return redirect(url_for('admin.policies'))
    
    return render_template('admin/add_policy.html')

@admin_bp.route('/reports')
@login_required
@admin_required
def reports():
    """System reports and analytics"""
    # Date range from request
    start_date = request.args.get('start_date', (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'))
    end_date = request.args.get('end_date', datetime.now().strftime('%Y-%m-%d'))
    
    # Convert to datetime objects
    start_dt = datetime.strptime(start_date, '%Y-%m-%d')
    end_dt = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
    
    # Usage statistics
    total_jobs = PrintJob.query.filter(PrintJob.created_at.between(start_dt, end_dt)).count()
    total_pages = db.session.query(func.sum(PrintJob.total_pages * PrintJob.copies))\
                           .filter(PrintJob.created_at.between(start_dt, end_dt)).scalar() or 0
    total_cost = db.session.query(func.sum(PrintJob.total_cost))\
                          .filter(PrintJob.created_at.between(start_dt, end_dt)).scalar() or 0
    
    # Top users
    top_users = db.session.query(
        User.username,
        func.count(PrintJob.id).label('job_count'),
        func.sum(PrintJob.total_pages * PrintJob.copies).label('total_pages'),
        func.sum(PrintJob.total_cost).label('total_cost')
    ).join(PrintJob).filter(PrintJob.created_at.between(start_dt, end_dt))\
     .group_by(User.username).order_by(desc('total_pages')).limit(10).all()
    
    # Department usage
    dept_stats = db.session.query(
        Department.name,
        func.count(PrintJob.id).label('job_count'),
        func.sum(PrintJob.total_pages * PrintJob.copies).label('total_pages'),
        func.sum(PrintJob.total_cost).label('total_cost')
    ).join(User).join(PrintJob).filter(PrintJob.created_at.between(start_dt, end_dt))\
     .group_by(Department.name).all()
    
    return render_template('admin/reports.html',
                         start_date=start_date,
                         end_date=end_date,
                         total_jobs=total_jobs,
                         total_pages=total_pages,
                         total_cost=total_cost,
                         top_users=top_users,
                         dept_stats=dept_stats)

@admin_bp.route('/settings')
@login_required
@admin_required
def settings():
    """System settings management"""
    settings = SystemSettings.query.all()
    settings_dict = {s.key: s.value for s in settings}
    
    return render_template('admin/settings.html', settings=settings_dict)

@admin_bp.route('/settings/update', methods=['POST'])
@login_required
@admin_required
def update_settings():
    """Update system settings"""
    for key, value in request.form.items():
        if key.startswith('setting_'):
            setting_key = key.replace('setting_', '')
            setting = SystemSettings.query.filter_by(key=setting_key).first()
            
            if setting:
                setting.value = value
                setting.updated_at = datetime.utcnow()
            else:
                setting = SystemSettings(
                    key=setting_key,
                    value=value,
                    description=f'Auto-created setting: {setting_key}'
                )
                db.session.add(setting)
    
    db.session.commit()
    flash('Settings updated successfully', 'success')
    return redirect(url_for('admin.settings'))


@admin_bp.route('/print-queue')
@login_required
@admin_required
def print_queue():
    """View incoming LPR jobs saved in the print queue"""
    queue = PrintQueue.query.order_by(PrintQueue.timestamp.desc()).all()
    return render_template('admin/print_queue.html', queue=queue)
