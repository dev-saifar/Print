from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_apscheduler import APScheduler
from flask_migrate import Migrate
from flask import redirect, url_for
from dotenv import load_dotenv
import os

# Load environment variables from .env
load_dotenv()

# Initialize extensions (no app yet)
db = SQLAlchemy()
scheduler = APScheduler()
migrate = Migrate()  # NEW: Initialize migrate

login_manager = LoginManager()
login_manager.login_view = 'main.login'
login_manager.login_message_category = 'info'

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-default-secret')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('SQLALCHEMY_DATABASE_URI', 'sqlite:///print.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # Initialize extensions with app
    db.init_app(app)
    migrate.init_app(app, db)  # ✅ Patch Migrate properly
    login_manager.init_app(app)
    scheduler.init_app(app)
    scheduler.start()

    from .routes import bp
    app.register_blueprint(bp)

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
