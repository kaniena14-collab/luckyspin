from datetime import datetime, timezone, timedelta
from app import db
from werkzeug.security import generate_password_hash, check_password_hash
import secrets
import string

# WIB Timezone (GMT+7)
WIB = timezone(timedelta(hours=7))

def wib_now():
    """Get current time in WIB timezone"""
    return datetime.now(WIB)

class Admin(db.Model):
    """Admin user model for authentication"""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=wib_now)
    
    def set_password(self, password):
        """Set password hash"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Check password against hash"""
        return check_password_hash(self.password_hash, password)

class Prize(db.Model):
    """Prize model for wheel prizes"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    icon_path = db.Column(db.String(500))  # Path to uploaded icon
    probability = db.Column(db.Float, default=10.0)  # Probability percentage (0-100)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=wib_now)
    
    def to_dict(self):
        """Convert prize to dictionary"""
        return {
            'id': self.id,
            'name': self.name,
            'icon_path': self.icon_path,
            'probability': self.probability,
            'is_active': self.is_active
        }

class Voucher(db.Model):
    """Voucher model for spin access control"""
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True, nullable=False)
    is_used = db.Column(db.Boolean, default=False)
    used_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=wib_now)
    # VIP Voucher fields
    is_vip = db.Column(db.Boolean, default=False)  # Mark as VIP voucher
    guaranteed_prize_id = db.Column(db.Integer, db.ForeignKey('prize.id'), nullable=True)  # Guaranteed prize for VIP
    vip_description = db.Column(db.String(200), nullable=True)  # Description for VIP voucher
    
    # Relationship
    guaranteed_prize = db.relationship('Prize', backref='vip_vouchers')
    
    @staticmethod
    def generate_code(length=8):
        """Generate random voucher code"""
        letters = string.ascii_uppercase + string.digits
        return ''.join(secrets.choice(letters) for _ in range(length))
    
    @staticmethod
    def generate_code_with_prefix(prefix='SBO', random_length=5):
        """Generate voucher code with custom prefix + 5 random digits"""
        digits = string.digits
        random_part = ''.join(secrets.choice(digits) for _ in range(random_length))
        return f"{prefix}{random_part}"
    
    def mark_used(self):
        """Mark voucher as used"""
        self.is_used = True
        self.used_at = wib_now()

class WheelSettings(db.Model):
    """Settings for wheel customization"""
    id = db.Column(db.Integer, primary_key=True)
    logo_path = db.Column(db.String(500))  # Brand logo
    background_path = db.Column(db.String(500))  # Background image
    wheel_color_1 = db.Column(db.String(7), default='#FF6B6B')  # Primary wheel color
    wheel_color_2 = db.Column(db.String(7), default='#4ECDC4')  # Secondary wheel color
    text_color = db.Column(db.String(7), default='#FFFFFF')  # Text color
    border_color = db.Column(db.String(7), default='#333333')  # Border color
    title_text = db.Column(db.String(200), default='Lucky Spin Wheel')  # Customizable title
    description_text = db.Column(db.String(500), default='Masukkan kode voucher Anda dan putar untuk memenangkan hadiah menarik!')  # Customizable description
    description_font_size = db.Column(db.Integer, default=18)  # Description font size
    description_color = db.Column(db.String(7), default='#ffffff')  # Description text color
    back_to_site_url = db.Column(db.String(500))  # Back to site link
    back_to_site_text = db.Column(db.String(100), default='Kembali ke Situs')  # Back button text
    input_bg_color = db.Column(db.String(7), default='#ffffff')  # Input background color
    input_text_color = db.Column(db.String(7), default='#000000')  # Input text color
    button_bg_color = db.Column(db.String(7), default='#ffc107')  # Button background color
    button_text_color = db.Column(db.String(7), default='#000000')  # Button text color
    # Popup settings
    popup_enabled = db.Column(db.Boolean, default=False)  # Enable/disable popup
    popup_title = db.Column(db.String(200), default='Selamat!')  # Popup title
    popup_description = db.Column(db.Text)  # Popup description
    popup_image_path = db.Column(db.String(500))  # Popup image
    popup_link_url = db.Column(db.String(500))  # Popup link URL
    popup_link_text = db.Column(db.String(100), default='Kunjungi Sekarang')  # Popup link text
    # Aura glow settings
    glow_enabled = db.Column(db.Boolean, default=True)  # Enable/disable glow effect
    glow_color = db.Column(db.String(7), default='#FF6B6B')  # Glow/aura color
    glow_intensity = db.Column(db.Integer, default=50)  # Glow intensity (0-100)
    # Center button settings
    center_button_bg_color = db.Column(db.String(7), default='#ffd700')  # Center button background
    center_button_text_color = db.Column(db.String(7), default='#000000')  # Center button text
    # Back button settings
    back_button_bg_color = db.Column(db.String(7), default='#007bff')  # Back button background
    back_button_text_color = db.Column(db.String(7), default='#ffffff')  # Back button text
    # Prize border settings
    prize_border_color = db.Column(db.String(7), default='#ffffff')  # Prize card border color
    prize_border_gradient_start = db.Column(db.String(7), default='#ff0000')  # Prize border gradient start color
    prize_border_gradient_end = db.Column(db.String(7), default='#9400d3')  # Prize border gradient end color
    # Container settings
    container_bg_color = db.Column(db.String(7), default='#1a1a2e')  # Main container background color
    # Background music settings
    music_path = db.Column(db.String(500))  # Background music file path
    # Spin sound settings
    spin_sound_path = db.Column(db.String(500))  # Spin sound effect file path
    updated_at = db.Column(db.DateTime, default=wib_now, onupdate=wib_now)
    
    @staticmethod
    def get_settings():
        """Get or create wheel settings"""
        settings = WheelSettings.query.first()
        if not settings:
            settings = WheelSettings()
            db.session.add(settings)
            db.session.commit()
        return settings

class SpinResult(db.Model):
    """Track spin results for analytics"""
    id = db.Column(db.Integer, primary_key=True)
    voucher_id = db.Column(db.Integer, db.ForeignKey('voucher.id'), nullable=False)
    prize_id = db.Column(db.Integer, db.ForeignKey('prize.id'), nullable=False)
    username = db.Column(db.String(100), nullable=True)  # Username pemenang
    spun_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    voucher = db.relationship('Voucher', backref='spin_results')
    prize = db.relationship('Prize', backref='spin_results')
