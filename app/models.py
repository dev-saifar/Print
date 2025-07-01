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
    released_at = db.Column(db.DateTime)  # When job was released for printing
    
    # Metadata
    printer_id = db.Column(db.Integer, db.ForeignKey('printer.id'))
    printer_name = db.Column(db.String(100), default='Default Printer')
    department_id = db.Column(db.Integer, db.ForeignKey('department.id'))
    notes = db.Column(db.Text)
    
    # Secure printing features
    print_code = db.Column(db.String(10))  # 6-digit print code for secure release
    secure_mode = db.Column(db.Boolean, default=False)  # If job requires authentication
    
    # File metadata
    file_size = db.Column(db.Integer)  # File size in bytes
    file_type = db.Column(db.String(20))  # pdf, docx, jpg, etc.
    
    # Cost tracking
    cost_per_page_bw = db.Column(db.Float, default=0.05)
    cost_per_page_color = db.Column(db.Float, default=0.15)
    applied_policy_id = db.Column(db.Integer, db.ForeignKey('print_policy.id'))
    
    def calculate_cost(self):
        """Calculate print job cost based on pricing rules and policies"""
        # Get pricing from department or system default
        pricing = PriceList.get_pricing_for_user(self.user_id)
        
        if self.color_mode == 'color':
            cost_per_page = pricing.cost_per_page_color
        else:
            cost_per_page = pricing.cost_per_page_bw
            
        # Apply duplex pricing
        if self.duplex:
            cost_per_page = pricing.cost_per_page_duplex
            
        # Calculate total sheets (duplex uses fewer sheets)
        total_sheets = self.total_pages * self.copies
        if self.duplex:
            total_sheets = (total_sheets + 1) // 2  # Round up for odd pages
            
        # Apply policy multipliers if applicable
        if self.applied_policy_id:
            policy = PrintPolicy.query.get(self.applied_policy_id)
            if policy:
                if self.color_mode == 'color':
                    cost_per_page *= policy.color_cost_multiplier
                else:
                    cost_per_page *= policy.bw_cost_multiplier
        
        self.total_cost = round(total_sheets * cost_per_page, 2)
        self.cost_per_page_bw = pricing.cost_per_page_bw
        self.cost_per_page_color = pricing.cost_per_page_color
        return self.total_cost
    
    def generate_print_code(self):
        """Generate secure 6-digit print code"""
        import random
        self.print_code = f"{random.randint(100000, 999999)}"
        return self.print_code

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

class PriceList(db.Model):
    """Pricing configuration for different user groups and departments"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text)
    
    # Per-page pricing
    cost_per_page_bw = db.Column(db.Float, default=0.05)  # Black & white
    cost_per_page_color = db.Column(db.Float, default=0.15)  # Color
    cost_per_page_duplex = db.Column(db.Float, default=0.04)  # Duplex (both sides)
    
    # Applicable to
    department_id = db.Column(db.Integer, db.ForeignKey('department.id'))
    user_role = db.Column(db.String(20))  # admin, user, guest
    is_default = db.Column(db.Boolean, default=False)
    
    # Metadata
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    @staticmethod
    def get_pricing_for_user(user_id):
        """Get applicable pricing for a user"""
        user = User.query.get(user_id)
        if not user:
            return PriceList.get_default_pricing()
        
        # Check department-specific pricing
        if user.department_id:
            dept_pricing = PriceList.query.filter_by(
                department_id=user.department_id, 
                is_active=True
            ).first()
            if dept_pricing:
                return dept_pricing
        
        # Check role-specific pricing
        role_pricing = PriceList.query.filter_by(
            user_role=user.role, 
            is_active=True
        ).first()
        if role_pricing:
            return role_pricing
        
        # Return default pricing
        return PriceList.get_default_pricing()
    
    @staticmethod
    def get_default_pricing():
        """Get default pricing configuration"""
        default = PriceList.query.filter_by(is_default=True, is_active=True).first()
        if not default:
            # Create default pricing if none exists
            default = PriceList(
                name="Default Pricing",
                description="System default pricing",
                cost_per_page_bw=0.05,
                cost_per_page_color=0.15,
                cost_per_page_duplex=0.04,
                is_default=True
            )
            db.session.add(default)
            db.session.commit()
        return default

class QuotaTracking(db.Model):
    """Track quota usage by user and time period"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Time period
    period_start = db.Column(db.DateTime, nullable=False)
    period_end = db.Column(db.DateTime, nullable=False)
    period_type = db.Column(db.String(20), default='monthly')  # daily, weekly, monthly, yearly
    
    # Usage tracking
    pages_printed = db.Column(db.Integer, default=0)
    pages_color = db.Column(db.Integer, default=0)
    pages_bw = db.Column(db.Integer, default=0)
    total_cost = db.Column(db.Float, default=0.0)
    job_count = db.Column(db.Integer, default=0)
    
    # Limits
    page_limit = db.Column(db.Integer)
    cost_limit = db.Column(db.Float)
    
    # Status
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    @staticmethod
    def get_current_quota(user_id):
        """Get current quota tracking for user"""
        from datetime import datetime, timedelta
        
        # Get current month period
        now = datetime.utcnow()
        period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if now.month == 12:
            period_end = period_start.replace(year=period_start.year + 1, month=1) - timedelta(days=1)
        else:
            period_end = period_start.replace(month=period_start.month + 1) - timedelta(days=1)
        
        quota = QuotaTracking.query.filter_by(
            user_id=user_id,
            period_start=period_start,
            period_type='monthly',
            is_active=True
        ).first()
        
        if not quota:
            user = User.query.get(user_id)
            quota = QuotaTracking(
                user_id=user_id,
                period_start=period_start,
                period_end=period_end,
                period_type='monthly',
                page_limit=user.quota_limit if user else 1000
            )
            db.session.add(quota)
            db.session.commit()
        
        return quota
    
    def add_usage(self, pages, color_pages, cost):
        """Add usage to quota tracking"""
        self.pages_printed += pages
        self.pages_color += color_pages
        self.pages_bw += (pages - color_pages)
        self.total_cost += cost
        self.job_count += 1
        self.updated_at = datetime.utcnow()

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

class PrintQueue(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255))
    user = db.Column(db.String(100))           # extracted from LPR
    user_ip = db.Column(db.String(100))
    queue_name = db.Column(db.String(50))
    status = db.Column(db.String(50), default="pending")
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    host = db.Column(db.String(100))           # H<hostname>
    job_size = db.Column(db.Integer)           # os.path.getsize(filepath)
    copies = db.Column(db.Integer, default=1)  # Optional
    printed_at = db.Column(db.DateTime)        # on release



