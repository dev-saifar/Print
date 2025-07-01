import os
import logging
import atexit
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from sqlalchemy.orm import DeclarativeBase
from werkzeug.middleware.proxy_fix import ProxyFix
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(level=logging.DEBUG)

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)
login_manager = LoginManager()
scheduler = BackgroundScheduler()


def create_app():
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.secret_key = os.environ.get("SESSION_SECRET")
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
        "DATABASE_URL", "sqlite:///database.db"
    )

    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_recycle": 300,
        "pool_pre_ping": True,
    }
    app.config["UPLOAD_FOLDER"] = os.path.join(app.root_path, "uploads")
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "main.login"
    login_manager.login_message = "Please log in to access this page."

    scheduler.start()
    atexit.register(lambda: scheduler.shutdown())

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    with app.app_context():
        from . import models  # noqa: F401
        from .routes import bp
        app.register_blueprint(bp)
        db.create_all()
        _create_default_data()

        # Start LPR listener thread
        from .lpr_server import start_lpr_server
        import threading
        threading.Thread(target=start_lpr_server, daemon=True).start()

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
        logging.info("Created default admin user (admin/admin123) and default department")


@login_manager.user_loader
def load_user(user_id):
    from .models import User
    return User.query.get(int(user_id))




