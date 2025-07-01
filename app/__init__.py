from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_apscheduler import APScheduler
from werkzeug.middleware.proxy_fix import ProxyFix
import os
import logging
import threading
from .lpr_server import start_lpr_server

# Initialize extensions (no app yet)
db = SQLAlchemy()
scheduler = APScheduler()

login_manager = LoginManager()
login_manager.login_view = 'main.login'
login_manager.login_message_category = 'info'

def create_app():
    app = Flask(__name__)
    
    # Configure for Replit environment
    app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key-change-in-production")
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
    
    # Database configuration
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_recycle": 300,
        "pool_pre_ping": True,
    }
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # File upload configuration
    app.config["UPLOAD_FOLDER"] = os.path.join(app.root_path, "uploads")
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    # Initialize extensions with app
    db.init_app(app)
    login_manager.init_app(app)
    scheduler.init_app(app)
    scheduler.start()

    # Register routes
    from .routes import bp
    app.register_blueprint(bp)

    # Create database tables
    with app.app_context():
        from . import models  # Import models to register them
        db.create_all()
        _create_default_data()

    # Start LPR server in background thread
    threading.Thread(target=start_lpr_server, args=(app,), daemon=True).start()

    return app

def _create_default_data():
    from .models import User, Department
    from werkzeug.security import generate_password_hash

    admin_user = User.query.filter_by(username="admin").first()
    if not admin_user:
        admin_user = User(
            username="admin",
            email="admin@company.com",
            password_hash=generate_password_hash("admin123"),
            role="admin",
            balance=1000.0,
            quota_limit=10000,
        )
        db.session.add(admin_user)

        default_dept = Department(name="General", description="Default department")
        db.session.add(default_dept)

        db.session.commit()
        logging.info("✅ Created default admin user and department")


@login_manager.user_loader
def load_user(user_id):
    from .models import User
    return User.query.get(int(user_id))
