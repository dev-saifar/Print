import os
import logging
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from sqlalchemy.orm import DeclarativeBase
from werkzeug.middleware.proxy_fix import ProxyFix
from apscheduler.schedulers.background import BackgroundScheduler
import atexit

# Configure logging
logging.basicConfig(level=logging.DEBUG)

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)

# Create the app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key-change-in-production")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Configure the database
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///printmanager.db"
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Initialize extensions
db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'

# Initialize scheduler for job processing
scheduler = BackgroundScheduler()
scheduler.start()
atexit.register(lambda: scheduler.shutdown())

# Create upload directory
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

with app.app_context():
    # Import models to ensure tables are created
    from models import User, PrintJob, Department
    from routes import *
    
    db.create_all()
    
    # Create default admin user if not exists
    from werkzeug.security import generate_password_hash
    admin_user = User.query.filter_by(username='admin').first()
    if not admin_user:
        admin_user = User(
            username='admin',
            email='admin@company.com',
            password_hash=generate_password_hash('admin123'),
            role='admin',
            balance=1000.0,
            quota_limit=10000
        )
        db.session.add(admin_user)
        
        # Create default department
        default_dept = Department(name='General', description='Default department')
        db.session.add(default_dept)
        
        db.session.commit()
        logging.info("Created default admin user (admin/admin123) and default department")

@login_manager.user_loader
def load_user(user_id):
    from models import User
    return User.query.get(int(user_id))
