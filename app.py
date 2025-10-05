import os
import logging
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from werkzeug.middleware.proxy_fix import ProxyFix
from replit.object_storage import Client

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
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///spinwheel.db")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Configure file uploads
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['UPLOAD_FOLDER'] = 'uploads'

# Ensure upload directory exists and is persistent
upload_folder = app.config['UPLOAD_FOLDER']
static_upload_folder = os.path.join('static', 'uploads')

# Create both directories
os.makedirs(upload_folder, exist_ok=True)
os.makedirs(static_upload_folder, exist_ok=True)

# Try to create symlink for better persistence (if not exists)
try:
    if not os.path.exists(os.path.join(upload_folder, '.persistent')):
        # Create marker file
        with open(os.path.join(upload_folder, '.persistent'), 'w') as f:
            f.write('This folder contains uploaded files')
    
    if not os.path.exists(os.path.join(static_upload_folder, '.backup')):
        # Create backup marker
        with open(os.path.join(static_upload_folder, '.backup'), 'w') as f:
            f.write('This is backup folder for uploads')
except Exception as e:
    logging.warning(f"Could not create persistence markers: {e}")

# Initialize Object Storage client (optional)
try:
    storage_client = Client()
    logging.info("Object Storage client initialized successfully")
except Exception as e:
    storage_client = None
    logging.warning(f"Object Storage not available (bucket not configured): {e}")
    logging.info("Using enhanced backup system instead")

# Initialize the app with the extension
db.init_app(app)

# Add timezone filter for templates
from datetime import datetime, timezone, timedelta

WIB = timezone(timedelta(hours=7))

@app.template_filter('wib')
def wib_filter(dt):
    """Convert datetime to WIB timezone and format"""
    if dt is None:
        return 'Belum Diatur'
    
    # If datetime is naive (no timezone), assume it's UTC
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    
    # Convert to WIB
    wib_time = dt.astimezone(WIB)
    return wib_time.strftime('%d/%m/%Y %H:%M WIB')

@app.template_filter('wib_date')
def wib_date_filter(dt):
    """Convert datetime to WIB date only"""
    if dt is None:
        return 'Belum Diatur'
    
    # If datetime is naive (no timezone), assume it's UTC
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    
    # Convert to WIB
    wib_time = dt.astimezone(WIB)
    return wib_time.strftime('%d/%m/%Y')

@app.template_filter('wib_time')
def wib_time_filter(dt):
    """Convert datetime to WIB time only"""
    if dt is None:
        return 'Belum Diatur'
    
    # If datetime is naive (no timezone), assume it's UTC
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    
    # Convert to WIB
    wib_time = dt.astimezone(WIB)
    return wib_time.strftime('%H:%M WIB')

with app.app_context():
    # Import models here so their tables are created
    import models  # noqa: F401
    db.create_all()
    logging.info("Database tables created")
