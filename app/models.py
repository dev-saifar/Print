from . import db
from flask_login import UserMixin
from datetime import datetime
from sqlalchemy import func

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), default='user')  # user, admin
    balance = db.Column(db.Float, default=0.0)
    quota_limit = db.Column(db.Integer, default=1000)  # pages per month
    quota_used = db.Column(db.Integer, default=0)
    department_id = db.Column(db.Integer, db.ForeignKey('department.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    
    # Relationships
    print_jobs = db.relationship('PrintJob', backref='user', lazy=True)
    department = db.relationship('Department', backref='users')
    
    def get_monthly_usage(self):
        """Get current month's page usage"""
        current_month = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return db.session.query(func.sum(PrintJob.total_pages)).filter(
            PrintJob.user_id == self.id,
            PrintJob.created_at >= current_month,
            PrintJob.status == 'completed'
        ).scalar() or 0
    
    def can_print(self, pages, cost):
        """Check if user can print based on quota and balance"""
        monthly_usage = self.get_monthly_usage()
        return (monthly_usage + pages <= self.quota_limit) and (self.balance >= cost)

class Department(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text)
    cost_center = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class PrintJob(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Print settings
    copies = db.Column(db.Integer, default=1)
    color_mode = db.Column(db.String(20), default='bw')  # bw, color
    duplex = db.Column(db.Boolean, default=False)
    paper_size = db.Column(db.String(20), default='A4')
    
    # Job details
    total_pages = db.Column(db.Integer, default=1)
    total_cost = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(20), default='pending')  # pending, printing, completed, failed, cancelled
    priority = db.Column(db.String(20), default='normal')  # low, normal, high
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    
    # Metadata
    printer_id = db.Column(db.Integer, db.ForeignKey('printer.id'))
    printer_name = db.Column(db.String(100), default='Default Printer')
    department_id = db.Column(db.Integer, db.ForeignKey('department.id'))
    notes = db.Column(db.Text)
    
    def calculate_cost(self):
        """Calculate print job cost based on pages, color, duplex"""
        base_cost_bw = 0.05  # $0.05 per B&W page
        base_cost_color = 0.15  # $0.15 per color page
        
        if self.color_mode == 'color':
            cost_per_page = base_cost_color
        else:
            cost_per_page = base_cost_bw
            
        # Duplex reduces cost slightly
        if self.duplex:
            cost_per_page *= 0.9
            
        total_sheets = self.total_pages * self.copies
        if self.duplex:
            total_sheets = (total_sheets + 1) // 2  # Round up for odd pages
            
        self.total_cost = round(total_sheets * cost_per_page, 2)
        return self.total_cost

class SystemSettings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.Text)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Printer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    model = db.Column(db.String(100))
    location = db.Column(db.String(200))
    ip_address = db.Column(db.String(45))
    port = db.Column(db.Integer, default=9100)
    
    # Printer capabilities
    supports_color = db.Column(db.Boolean, default=True)
    supports_duplex = db.Column(db.Boolean, default=True)
    supports_scanning = db.Column(db.Boolean, default=False)
    max_paper_size = db.Column(db.String(20), default='A4')
    
    # Status and monitoring
    status = db.Column(db.String(20), default='offline')
    toner_level = db.Column(db.Integer, default=100)
    paper_level = db.Column(db.Integer, default=100)
    total_pages_printed = db.Column(db.Integer, default=0)
    
    # Settings
    is_active = db.Column(db.Boolean, default=True)
    is_default = db.Column(db.Boolean, default=False)
    department_id = db.Column(db.Integer, db.ForeignKey('department.id'))
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_seen = db.Column(db.DateTime)

class PrintPolicy(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text)
    
    # Policy rules
    force_duplex_over_pages = db.Column(db.Integer, default=0)
    force_bw_over_pages = db.Column(db.Integer, default=0)
    max_pages_per_job = db.Column(db.Integer, default=0)
    max_copies = db.Column(db.Integer, default=10)
    
    # Cost multipliers
    color_cost_multiplier = db.Column(db.Float, default=1.0)
    bw_cost_multiplier = db.Column(db.Float, default=1.0)
    
    # Time restrictions
    allowed_start_time = db.Column(db.Time)
    allowed_end_time = db.Column(db.Time)
    
    # Department/user restrictions
    department_id = db.Column(db.Integer, db.ForeignKey('department.id'))
    user_role = db.Column(db.String(20))
    
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class PrintQueue(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    user_ip = db.Column(db.String(100), nullable=False)
    username = db.Column(db.String(100), nullable=True)  # LPR username
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(50), default="pending")
    pages = db.Column(db.Integer, default=1)
    copies = db.Column(db.Integer, default=1)
    printer_used = db.Column(db.String(100), nullable=True)
    queue_name = db.Column(db.String(100), nullable=True)  # ✅ Add this line

def init_app(app):
    db.init_app(app)
    migrate.init_app(app, db)
