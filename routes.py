import os
import random
import secrets
import threading
from datetime import datetime
from flask import render_template, request, redirect, url_for, flash, session, jsonify, send_from_directory, Response
from werkzeug.utils import secure_filename
from PIL import Image
import logging
import io

from app import app, db, storage_client
from models import Admin, Prize, Voucher, WheelSettings, SpinResult, wib_now

# Allowed file extensions for uploads
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'svg', 'webp', 'bmp', 'tiff', 'tif', 'ico'}
ALLOWED_AUDIO_EXTENSIONS = {'mp3', 'wav', 'ogg', 'm4a', 'aac', 'flac', 'wma', 'opus', 'mp4'}

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def allowed_audio_file(filename):
    """Check if audio file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_AUDIO_EXTENSIONS

def save_to_storage(file_content, filename):
    """Save file with multiple backup redundancy"""
    try:
        # Save to multiple locations for maximum persistence
        locations_saved = 0
        
        # 1. Save to main upload folder
        try:
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            with open(file_path, 'wb') as f:
                f.write(file_content)
            locations_saved += 1
            logging.info(f"File saved to main uploads: {filename}")
        except Exception as e:
            logging.error(f"Error saving to main uploads: {e}")
        
        # 2. Save to static/uploads backup
        try:
            static_folder = os.path.join('static', 'uploads')
            os.makedirs(static_folder, exist_ok=True)
            backup_path = os.path.join(static_folder, filename)
            with open(backup_path, 'wb') as f:
                f.write(file_content)
            locations_saved += 1
            logging.info(f"File saved to static backup: {filename}")
        except Exception as e:
            logging.error(f"Error saving to static backup: {e}")
        
        # 3. Try Object Storage if available (best for persistence)
        try:
            if storage_client:
                storage_client.upload_from_bytes(filename, file_content)
                locations_saved += 1
                logging.info(f"File saved to Object Storage: {filename}")
        except Exception as e:
            logging.warning(f"Object Storage upload failed: {e}")
        
        # 4. Create additional backup in home directory (most persistent)
        try:
            home_backup = os.path.join(os.path.expanduser('~'), '.app_backups')
            os.makedirs(home_backup, exist_ok=True)
            home_path = os.path.join(home_backup, filename)
            with open(home_path, 'wb') as f:
                f.write(file_content)
            locations_saved += 1
            logging.info(f"File saved to home backup: {filename}")
        except Exception as e:
            logging.warning(f"Home backup failed: {e}")
        
        if locations_saved > 0:
            logging.info(f"File {filename} saved to {locations_saved} locations")
            return filename
        else:
            raise Exception("Failed to save file to any location")
            
    except Exception as e:
        logging.error(f"Critical error saving file {filename}: {e}")
        raise

def get_from_storage(filename):
    """Get file content from multiple backup locations"""
    try:
        # Priority order for file retrieval
        search_locations = [
            # 1. Object Storage (if available) - most persistent
            lambda: storage_client.download_as_bytes(filename) if storage_client else None,
            # 2. Home backup directory - most persistent on filesystem
            lambda: open(os.path.join(os.path.expanduser('~'), '.app_backups', filename), 'rb').read(),
            # 3. Main uploads folder
            lambda: open(os.path.join(app.config['UPLOAD_FOLDER'], filename), 'rb').read(),
            # 4. Static uploads backup
            lambda: open(os.path.join('static', 'uploads', filename), 'rb').read(),
        ]
        
        for i, get_file in enumerate(search_locations):
            try:
                file_content = get_file()
                if file_content:
                    location_names = ["Object Storage", "Home backup", "Main uploads", "Static backup"]
                    logging.info(f"File {filename} retrieved from {location_names[i]}")
                    
                    # Auto-restore to other locations if found in backup
                    if i > 0:  # If not from primary location, restore to others
                        threading.Thread(target=restore_to_all_locations, args=(filename, file_content)).start()
                    
                    return file_content
            except Exception as e:
                continue  # Try next location
        
        logging.warning(f"File {filename} not found in any backup location")
        return None
        
    except Exception as e:
        logging.error(f"Error retrieving file {filename}: {e}")
        return None

def restore_to_all_locations(filename, file_content):
    """Background task to restore file to all backup locations"""
    try:
        save_to_storage(file_content, filename)
        logging.info(f"File {filename} restored to all backup locations")
    except Exception as e:
        logging.error(f"Error restoring file {filename}: {e}")

def resize_image(image_path, max_size=(300, 300)):
    """Resize uploaded image to max dimensions"""
    try:
        # Skip processing for certain formats to preserve their properties
        file_ext = image_path.lower().split('.')[-1]
        
        if file_ext in ['gif', 'svg', 'ico']:
            # Just check file size and return for special formats
            file_size = os.path.getsize(image_path)
            if file_size > 10 * 1024 * 1024:  # 10MB limit for special formats
                logging.warning(f"Special format file {image_path} is too large ({file_size} bytes)")
            return
        
        with Image.open(image_path) as img:
            original_format = img.format
            
            # Preserve transparency for formats that support it
            if original_format in ['PNG', 'WEBP'] and img.mode in ('RGBA', 'LA'):
                # Keep RGBA mode for transparency
                pass
            elif img.mode in ('RGBA', 'LA', 'P'):
                # Convert to RGB for other formats
                img = img.convert('RGB')
            
            # Resize maintaining aspect ratio
            img.thumbnail(max_size, Image.Resampling.LANCZOS)
            
            # Save in original format if possible, otherwise use PNG for transparency
            if original_format in ['PNG', 'WEBP'] and img.mode == 'RGBA':
                img.save(image_path, original_format, quality=85, optimize=True)
            elif original_format == 'PNG':
                img.save(image_path, 'PNG', quality=85, optimize=True)
            else:
                img.save(image_path, 'JPEG', quality=85)
    except Exception as e:
        logging.error(f"Error resizing image {image_path}: {e}")

def is_admin_logged_in():
    """Check if admin is logged in"""
    return 'admin_id' in session

def admin_required(f):
    """Decorator to require admin login"""
    def decorated_function(*args, **kwargs):
        if not is_admin_logged_in():
            flash('Please login as admin to access this page.', 'error')
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

# Public Routes
@app.route('/')
def index():
    """Main spin wheel page"""
    settings = WheelSettings.get_settings()
    prizes = Prize.query.filter_by(is_active=True).all()
    # Convert prizes to dictionaries for JSON serialization
    prizes_data = [prize.to_dict() for prize in prizes]
    return render_template('index.html', settings=settings, prizes=prizes_data)

@app.route('/spin', methods=['POST'])
def spin_wheel():
    """Handle spin wheel request"""
    voucher_code = request.form.get('voucher_code', '').strip().upper()
    
    if not voucher_code:
        return jsonify({'error': 'Please enter a voucher code'}), 400
    
    # Validate voucher
    voucher = Voucher.query.filter_by(code=voucher_code, is_used=False).first()
    if not voucher:
        return jsonify({'error': 'Invalid or already used voucher code'}), 400
    
    # Get active prizes (needed for both VIP and regular vouchers)
    prizes = Prize.query.filter_by(is_active=True).all()
    if not prizes:
        return jsonify({'error': 'No prizes available'}), 400
    
    # Check if this is a VIP voucher with guaranteed prize
    if voucher.is_vip and voucher.guaranteed_prize_id:
        winner = Prize.query.get(voucher.guaranteed_prize_id)
        if not winner or not winner.is_active:
            return jsonify({'error': 'VIP prize is no longer available'}), 400
    else:
        # Regular voucher - use probability system
        
        # Calculate weighted random selection
        weights = [prize.probability for prize in prizes]
        total_weight = sum(weights)
        
        if total_weight <= 0:
            return jsonify({'error': 'No prizes with valid probabilities'}), 400
        
        # Select winner based on probability weights
        rand_val = random.uniform(0, total_weight)
        cumulative = 0
        winner = None
        
        for prize in prizes:
            cumulative += prize.probability
            if rand_val <= cumulative:
                winner = prize
                break
        
        if not winner:
            winner = prizes[-1]  # Fallback to last prize
    
    # Mark voucher as used
    voucher.mark_used()
    
    # Record spin result
    spin_result = SpinResult()
    spin_result.voucher_id = voucher.id
    spin_result.prize_id = winner.id
    db.session.add(spin_result)
    db.session.commit()
    
    # Calculate rotation angle for animation
    prize_count = len(prizes)
    segment_angle = 360 / prize_count
    winner_index = next(i for i, p in enumerate(prizes) if p.id == winner.id)
    
    # Add multiple full rotations plus angle to winner segment
    base_rotations = random.randint(5, 8) * 360
    winner_angle = winner_index * segment_angle + (segment_angle / 2)
    final_angle = base_rotations + (360 - winner_angle)  # Invert because wheel spins clockwise
    
    return jsonify({
        'success': True,
        'prize': winner.to_dict(),
        'rotation': final_angle,
        'spin_id': spin_result.id
    })

@app.route('/save_username', methods=['POST'])
def save_username():
    """Save username for spin result"""
    spin_id = request.form.get('spin_id')
    username = request.form.get('username', '').strip()
    
    if not spin_id or not username:
        return jsonify({'error': 'Missing spin ID or username'}), 400
    
    # Find spin result
    spin_result = SpinResult.query.get(spin_id)
    if not spin_result:
        return jsonify({'error': 'Spin result not found'}), 404
    
    # Update username
    spin_result.username = username
    db.session.commit()
    
    return jsonify({'success': True})

# Admin Routes
@app.route('/admin')
def admin_login():
    """Admin login page"""
    if is_admin_logged_in():
        return redirect(url_for('admin_dashboard'))
    return render_template('admin/login.html')

@app.route('/admin/login', methods=['POST'])
def admin_login_post():
    """Handle admin login"""
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '')
    
    if not username or not password:
        flash('Please enter both username and password.', 'error')
        return redirect(url_for('admin_login'))
    
    # Check if admin exists, create default admin if none exist
    admin = Admin.query.filter_by(username=username).first()
    if not admin:
        admin_count = Admin.query.count()
        if admin_count == 0 and username == 'admin':
            # Create default admin account
            default_admin = Admin()
            default_admin.username = 'admin'
            default_admin.set_password('bell2026')
            db.session.add(default_admin)
            db.session.commit()
            admin = default_admin
            flash('Default admin account created. Please change the password.', 'info')
    
    if admin and admin.check_password(password):
        session['admin_id'] = admin.id
        flash('Successfully logged in!', 'success')
        return redirect(url_for('admin_dashboard'))
    else:
        flash('Invalid username or password.', 'error')
        return redirect(url_for('admin_login'))

@app.route('/admin/logout')
def admin_logout():
    """Admin logout"""
    session.pop('admin_id', None)
    flash('Successfully logged out.', 'success')
    return redirect(url_for('index'))

@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    """Admin dashboard"""
    prize_count = Prize.query.count()
    voucher_count = Voucher.query.filter_by(is_used=False, is_vip=False).count()
    used_voucher_count = Voucher.query.filter_by(is_used=True).count()
    vip_voucher_count = Voucher.query.filter_by(is_vip=True).count()
    spin_count = SpinResult.query.count()
    
    stats = {
        'prizes': prize_count,
        'active_vouchers': voucher_count,
        'used_vouchers': used_voucher_count,
        'vip_vouchers': vip_voucher_count,
        'total_spins': spin_count
    }
    
    return render_template('admin/dashboard.html', stats=stats)

@app.route('/admin/prizes')
@admin_required
def admin_prizes():
    """Prize management page"""
    from sqlalchemy import desc
    page = request.args.get('page', 1, type=int)
    per_page = 20  # Show 20 prizes per page
    
    prizes_pagination = Prize.query.order_by(desc(Prize.created_at)).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return render_template('admin/prizes.html', 
                         prizes=prizes_pagination.items,
                         pagination=prizes_pagination,
                         current_page=page)

@app.route('/admin/prizes/add', methods=['POST'])
@admin_required
def admin_add_prize():
    """Add new prize"""
    name = request.form.get('name', '').strip()
    probability = float(request.form.get('probability', 10))
    
    if not name:
        flash('Prize name is required.', 'error')
        page = request.form.get('page', '1')
        return redirect(url_for('admin_prizes', page=page))
    
    if probability < 0 or probability > 100:
        flash('Probability must be between 0 and 100.', 'error')
        page = request.form.get('page', '1')
        return redirect(url_for('admin_prizes', page=page))
    
    prize = Prize()
    prize.name = name
    prize.probability = probability
    
    # Handle icon upload
    if 'icon' in request.files:
        file = request.files['icon']
        if file and file.filename and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            # Add timestamp to avoid conflicts
            timestamp = str(int(datetime.now().timestamp()))
            filename = f"{timestamp}_{filename}"
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            
            # Resize image if it's not SVG
            if not filename.lower().endswith('.svg'):
                resize_image(file_path)
            
            prize.icon_path = filename
    
    db.session.add(prize)
    db.session.commit()
    flash('Prize added successfully!', 'success')
    page = request.form.get('page', '1')
    return redirect(url_for('admin_prizes', page=page))

@app.route('/admin/prizes/edit/<int:prize_id>', methods=['POST'])
@admin_required
def admin_edit_prize(prize_id):
    """Edit existing prize"""
    prize = Prize.query.get_or_404(prize_id)
    
    name = request.form.get('name', '').strip()
    probability = float(request.form.get('probability', 10))
    is_active = 'is_active' in request.form
    
    if not name:
        flash('Prize name is required.', 'error')
        page = request.form.get('page', '1')
        return redirect(url_for('admin_prizes', page=page))
    
    if probability < 0 or probability > 100:
        flash('Probability must be between 0 and 100.', 'error')
        page = request.form.get('page', '1')
        return redirect(url_for('admin_prizes', page=page))
    
    prize.name = name
    prize.probability = probability
    prize.is_active = is_active
    
    # Handle icon upload
    if 'icon' in request.files:
        file = request.files['icon']
        if file and file.filename and allowed_file(file.filename):
            # Delete old icon if exists
            if prize.icon_path:
                old_path = os.path.join(app.config['UPLOAD_FOLDER'], prize.icon_path)
                if os.path.exists(old_path):
                    os.remove(old_path)
            
            filename = secure_filename(file.filename)
            timestamp = str(int(datetime.now().timestamp()))
            filename = f"{timestamp}_{filename}"
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            
            if not filename.lower().endswith('.svg'):
                resize_image(file_path)
            
            prize.icon_path = filename
    
    db.session.commit()
    flash('Prize updated successfully!', 'success')
    page = request.form.get('page', '1')
    return redirect(url_for('admin_prizes', page=page))

@app.route('/admin/prizes/delete/<int:prize_id>', methods=['POST'])
@admin_required
def admin_delete_prize(prize_id):
    """Delete prize and related records"""
    try:
        prize = Prize.query.get_or_404(prize_id)
        
        # Check if force delete is requested
        force_delete = request.form.get('force_delete', '0') == '1'
        
        # Check if prize is referenced by any spin results
        spin_results = SpinResult.query.filter_by(prize_id=prize_id).all()
        
        if spin_results and not force_delete:
            # Return warning message with option to force delete
            flash(f'Hadiah ini sudah digunakan dalam {len(spin_results)} history spin. Klik "Hapus Paksa" untuk menghapus hadiah beserta historynya.', 'warning')
            page = request.form.get('page', '1')
            return redirect(url_for('admin_prizes', page=page, warning_prize_id=prize_id))
        
        # Delete related spin results first if force delete
        if spin_results:
            for spin_result in spin_results:
                db.session.delete(spin_result)
            flash(f'Menghapus {len(spin_results)} history spin terkait...', 'info')
        
        # Delete icon file if exists
        if prize.icon_path:
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], prize.icon_path)
            if os.path.exists(file_path):
                os.remove(file_path)
        
        # Delete the prize
        db.session.delete(prize)
        db.session.commit()
        flash('Hadiah berhasil dihapus!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Terjadi kesalahan saat menghapus hadiah: {str(e)}', 'error')
    
    page = request.form.get('page', '1')
    return redirect(url_for('admin_prizes', page=page))

@app.route('/admin/prizes/bulk-upload-icons', methods=['POST'])
@admin_required
def admin_bulk_upload_icons():
    """Bulk upload icons for existing prizes"""
    try:
        updated_count = 0
        skipped_count = 0
        error_count = 0
        
        # Get all prizes for reference
        all_prizes = {str(prize.id): prize for prize in Prize.query.all()}
        
        # Process each uploaded file
        for field_name in request.files:
            if not field_name.startswith('icon_'):
                continue
                
            try:
                # Extract prize ID from field name (icon_123 -> 123)
                prize_id = field_name.replace('icon_', '')
                
                if prize_id not in all_prizes:
                    skipped_count += 1
                    continue
                    
                prize = all_prizes[prize_id]
                file = request.files[field_name]
                
                if not file or not file.filename:
                    skipped_count += 1
                    continue
                    
                if not allowed_file(file.filename):
                    flash(f'File untuk hadiah "{prize.name}" memiliki format yang tidak diizinkan.', 'warning')
                    error_count += 1
                    continue
                
                # Generate unique filename
                filename = secure_filename(file.filename)
                timestamp = str(int(datetime.now().timestamp()))
                filename = f"{timestamp}_{filename}"
                
                # Save file to temporary location first
                temp_path = os.path.join(app.config['UPLOAD_FOLDER'], f"temp_{filename}")
                file.save(temp_path)
                
                # Resize if not SVG
                if not filename.lower().endswith('.svg'):
                    resize_image(temp_path)
                
                # Use the multi-location save system
                file_content = open(temp_path, 'rb').read()
                save_to_storage(file_content, filename)
                
                # Clean up temp file
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                
                # Update prize icon path (no need to delete old file, keep for backup)
                prize.icon_path = filename
                updated_count += 1
                
                logging.info(f"Bulk upload: Updated icon for prize {prize.name} (ID: {prize.id})")
                
            except Exception as e:
                error_count += 1
                logging.error(f"Error processing bulk upload for field {field_name}: {e}")
                continue
        
        # Commit all changes at once
        if updated_count > 0:
            db.session.commit()
            flash(f'Berhasil mengupdate {updated_count} icon hadiah!', 'success')
        
        if skipped_count > 0:
            flash(f'{skipped_count} file dilewati (tidak ada file atau hadiah tidak ditemukan).', 'info')
            
        if error_count > 0:
            flash(f'{error_count} file gagal diproses karena error.', 'warning')
            
        if updated_count == 0 and skipped_count == 0 and error_count == 0:
            flash('Tidak ada file yang dipilih untuk diupload.', 'info')
            
    except Exception as e:
        db.session.rollback()
        logging.error(f"Bulk upload error: {e}")
        flash(f'Terjadi kesalahan saat upload massal: {str(e)}', 'error')
    
    return redirect(url_for('admin_prizes'))

@app.route('/admin/vouchers')
@admin_required
def admin_vouchers():
    """Voucher management page"""
    from sqlalchemy import desc
    active_vouchers = Voucher.query.filter_by(is_used=False).order_by(desc(Voucher.created_at)).all()
    used_vouchers = Voucher.query.filter_by(is_used=True).filter(Voucher.used_at.isnot(None)).order_by(desc(Voucher.used_at)).limit(50).all()
    return render_template('admin/vouchers.html', active_vouchers=active_vouchers, used_vouchers=used_vouchers)

@app.route('/admin/vouchers/generate', methods=['POST'])
@admin_required
def admin_generate_vouchers():
    """Generate new vouchers"""
    try:
        count = int(request.form.get('count', 1))
        prefix = request.form.get('prefix', 'SBO').strip().upper()
        
        if count < 1 or count > 1000:
            flash('Count must be between 1 and 1000.', 'error')
            return redirect(url_for('admin_vouchers'))
        
        if len(prefix) > 10:
            flash('Prefix tidak boleh lebih dari 10 karakter.', 'error')
            return redirect(url_for('admin_vouchers'))
        
        vouchers = []
        for _ in range(count):
            code = Voucher.generate_code_with_prefix(prefix)
            # Ensure uniqueness
            while Voucher.query.filter_by(code=code).first():
                code = Voucher.generate_code_with_prefix(prefix)
            
            voucher = Voucher()
            voucher.code = code
            vouchers.append(voucher)
        
        db.session.add_all(vouchers)
        db.session.commit()
        flash(f'{count} voucher dengan prefix "{prefix}" berhasil dibuat!', 'success')
    except ValueError:
        flash('Invalid count value.', 'error')
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
    
    return redirect(url_for('admin_vouchers'))

@app.route('/admin/vouchers/delete/<int:voucher_id>', methods=['POST'])
@admin_required
def admin_delete_voucher(voucher_id):
    """Delete voucher"""
    voucher = Voucher.query.get_or_404(voucher_id)
    db.session.delete(voucher)
    db.session.commit()
    flash('Voucher deleted successfully!', 'success')
    return redirect(url_for('admin_vouchers'))

@app.route('/admin/vouchers/bulk-delete', methods=['POST'])
@admin_required
def admin_bulk_delete_vouchers():
    """Bulk delete vouchers"""
    try:
        data = request.get_json()
        voucher_ids = data.get('voucher_ids', [])
        voucher_type = data.get('type', 'active')  # 'active' or 'used'
        
        if not voucher_ids:
            return jsonify({'success': False, 'message': 'Tidak ada voucher yang dipilih'})
        
        count = 0
        for voucher_id in voucher_ids:
            voucher = Voucher.query.get(voucher_id)
            if voucher:
                # Check type validity
                if voucher_type == 'active' and voucher.is_used:
                    continue  # Skip used vouchers when deleting active ones
                elif voucher_type == 'used' and not voucher.is_used:
                    continue  # Skip active vouchers when deleting used ones
                
                db.session.delete(voucher)
                count += 1
        
        db.session.commit()
        return jsonify({
            'success': True, 
            'message': f'{count} voucher berhasil dihapus',
            'deleted_count': count
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Terjadi kesalahan: {str(e)}'})

# VIP Voucher Management Routes
@app.route('/admin/vip-vouchers')
@admin_required
def admin_vip_vouchers():
    """VIP vouchers management page"""
    vip_vouchers = Voucher.query.filter_by(is_vip=True).order_by(Voucher.created_at.desc()).all()
    prizes = Prize.query.filter_by(is_active=True).all()
    return render_template('admin/vip_vouchers.html', vip_vouchers=vip_vouchers, prizes=prizes)

@app.route('/admin/vip-vouchers/create', methods=['POST'])
@admin_required
def admin_create_vip_voucher():
    """Create new VIP voucher"""
    voucher_code = request.form.get('voucher_code', '').strip().upper()
    prefix = request.form.get('prefix', 'SBO').strip().upper()
    vip_description = request.form.get('vip_description', '').strip()
    guaranteed_prize_id = request.form.get('guaranteed_prize_id')
    
    # Validate prize exists
    prize = Prize.query.get(guaranteed_prize_id)
    if not prize:
        flash('Hadiah yang dipilih tidak ada!', 'error')
        return redirect(url_for('admin_vip_vouchers'))
    
    # Validate prefix
    if len(prefix) > 10:
        flash('Prefix tidak boleh lebih dari 10 karakter.', 'error')
        return redirect(url_for('admin_vip_vouchers'))
    
    # Generate code if not provided
    if not voucher_code:
        voucher_code = Voucher.generate_code_with_prefix(prefix)
        # Ensure uniqueness
        while Voucher.query.filter_by(code=voucher_code).first():
            voucher_code = Voucher.generate_code_with_prefix(prefix)
    else:
        # Check if code already exists
        if Voucher.query.filter_by(code=voucher_code).first():
            flash('Kode voucher sudah ada! Silakan pilih kode yang berbeda.', 'error')
            return redirect(url_for('admin_vip_vouchers'))
    
    # Create VIP voucher
    vip_voucher = Voucher()
    vip_voucher.code = voucher_code
    vip_voucher.is_vip = True
    vip_voucher.guaranteed_prize_id = guaranteed_prize_id
    vip_voucher.vip_description = vip_description if vip_description else None
    
    db.session.add(vip_voucher)
    db.session.commit()
    
    flash(f'VIP voucher "{voucher_code}" berhasil dibuat! Hadiah terjamin: {prize.name}', 'success')
    return redirect(url_for('admin_vip_vouchers'))

@app.route('/admin/vip-vouchers/delete/<int:voucher_id>', methods=['POST'])
@admin_required
def admin_delete_vip_voucher(voucher_id):
    """Delete VIP voucher"""
    try:
        voucher = Voucher.query.get_or_404(voucher_id)
        if not voucher.is_vip:
            return jsonify({'success': False, 'message': 'Not a VIP voucher'})
        
        db.session.delete(voucher)
        db.session.commit()
        return jsonify({'success': True, 'message': 'VIP voucher deleted successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})

@app.route('/admin/vip-vouchers/bulk-delete', methods=['POST'])
@admin_required
def admin_bulk_delete_vip_vouchers():
    """Bulk delete VIP vouchers"""
    try:
        data = request.get_json()
        voucher_ids = data.get('voucher_ids', [])
        
        if not voucher_ids:
            return jsonify({'success': False, 'message': 'Tidak ada voucher yang dipilih'})
        
        # Find and delete VIP vouchers
        deleted_count = 0
        for voucher_id in voucher_ids:
            voucher = Voucher.query.get(voucher_id)
            if voucher and voucher.is_vip:
                db.session.delete(voucher)
                deleted_count += 1
        
        db.session.commit()
        
        if deleted_count > 0:
            return jsonify({'success': True, 'message': f'{deleted_count} VIP voucher berhasil dihapus'})
        else:
            return jsonify({'success': False, 'message': 'Tidak ada VIP voucher yang valid untuk dihapus.'})
            
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})

@app.route('/admin/winners')
@admin_required
def admin_winners():
    """Winners tracking page"""
    from sqlalchemy import desc
    # Get all spin results with prize and voucher information
    winners = db.session.query(SpinResult, Prize, Voucher).join(
        Prize, SpinResult.prize_id == Prize.id
    ).join(
        Voucher, SpinResult.voucher_id == Voucher.id
    ).order_by(desc(SpinResult.spun_at)).limit(100).all()
    
    return render_template('admin/winners.html', winners=winners)

@app.route('/admin/winners/delete', methods=['POST'])
@admin_required
def admin_delete_winners():
    """Delete selected winners"""
    winner_ids = request.form.getlist('winner_ids')
    
    if not winner_ids:
        flash('Tidak ada pemenang yang dipilih untuk dihapus.', 'error')
        return redirect(url_for('admin_winners'))
    
    try:
        # Delete selected spin results
        count = 0
        for winner_id in winner_ids:
            spin_result = SpinResult.query.get(winner_id)
            if spin_result:
                db.session.delete(spin_result)
                count += 1
        
        db.session.commit()
        flash(f'{count} history pemenang berhasil dihapus!', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Terjadi kesalahan saat menghapus history.', 'error')
    
    return redirect(url_for('admin_winners'))

@app.route('/admin/history')
@admin_required
def admin_history():
    """View spin history"""
    from sqlalchemy import desc
    spin_results = db.session.query(SpinResult, Prize, Voucher).join(
        Prize, SpinResult.prize_id == Prize.id
    ).join(
        Voucher, SpinResult.voucher_id == Voucher.id
    ).order_by(desc(SpinResult.spun_at)).all()
    
    # Transform data for template
    history_data = []
    for spin_result, prize, voucher in spin_results:
        history_data.append({
            'id': spin_result.id,
            'created_at': spin_result.spun_at,
            'username': spin_result.username,
            'voucher_code': voucher.code,
            'prize': prize
        })
    
    return render_template('admin/history.html', spin_results=history_data)

@app.route('/admin/history/delete', methods=['POST'])
@admin_required
def admin_delete_history():
    """Delete selected history entries"""
    try:
        data = request.get_json()
        ids = data.get('ids', [])
        
        if not ids:
            return jsonify({'success': False, 'message': 'No IDs provided'})
        
        count = 0
        for history_id in ids:
            spin_result = SpinResult.query.get(history_id)
            if spin_result:
                db.session.delete(spin_result)
                count += 1
        
        db.session.commit()
        return jsonify({'success': True, 'message': f'{count} history entries deleted'})
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})

@app.route('/admin/history/clear')
@admin_required
def admin_clear_history():
    """Clear all history"""
    try:
        count = SpinResult.query.count()
        SpinResult.query.delete()
        db.session.commit()
        flash(f'{count} history entries cleared successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Error clearing history.', 'error')
    
    return redirect(url_for('admin_history'))

@app.route('/admin/settings')
@admin_required
def admin_settings():
    """Wheel settings page"""
    settings = WheelSettings.get_settings()
    return render_template('admin/settings.html', settings=settings)

@app.route('/admin/account-settings')
@admin_required
def admin_account_settings():
    """Account settings page"""
    settings = WheelSettings.get_settings()
    return render_template('admin/account_settings.html', settings=settings)

@app.route('/admin/update-logo', methods=['POST'])
@admin_required
def admin_update_logo():
    """Update application logo with password protection"""
    SECRET_PASSWORD = 'bell2027'
    
    # Verifikasi password
    verified_password = request.form.get('verified_password', '')
    if verified_password != SECRET_PASSWORD:
        flash('Password tidak valid! Akses ditolak.', 'error')
        return redirect(url_for('admin_account_settings'))
    
    # Proses upload logo
    if 'logo_file' not in request.files:
        flash('Tidak ada file yang dipilih.', 'error')
        return redirect(url_for('admin_account_settings'))
    
    file = request.files['logo_file']
    if file.filename == '':
        flash('Tidak ada file yang dipilih.', 'error')
        return redirect(url_for('admin_account_settings'))
    
    # Validasi file
    allowed_extensions = {'png', 'jpg', 'jpeg', 'gif'}
    if not file.filename or not ('.' in file.filename and file.filename.rsplit('.', 1)[1].lower() in allowed_extensions):
        flash('Format file tidak didukung! Gunakan PNG, JPG, JPEG, atau GIF.', 'error')
        return redirect(url_for('admin_account_settings'))
    
    try:
        # Simpan file
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_')
        filename = timestamp + filename
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        # Buat direktori jika belum ada
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        
        # Resize dan simpan gambar
        from PIL import Image
        import shutil
        
        # Save file first then open it
        file.save(file_path)
        
        # Create backup copy in static folder for better persistence
        static_backup_path = os.path.join('static', 'uploads', filename)
        os.makedirs(os.path.dirname(static_backup_path), exist_ok=True)
        shutil.copy2(file_path, static_backup_path)
        
        image = Image.open(file_path)
        
        # Convert RGBA to RGB if necessary
        if image.mode == 'RGBA':
            background = Image.new('RGB', image.size, (255, 255, 255))
            background.paste(image, mask=image.split()[-1] if image.mode == 'RGBA' else None)
            image = background
        
        # Resize logo ke ukuran maksimal 300x300 sambil mempertahankan aspect ratio
        image.thumbnail((300, 300), Image.Resampling.LANCZOS)
        image.save(file_path, optimize=True, quality=90)
        
        # Update database
        settings = WheelSettings.get_settings()
        
        # Hapus logo lama jika ada
        if settings.logo_path:
            old_path = os.path.join(app.config['UPLOAD_FOLDER'], settings.logo_path)
            if os.path.exists(old_path):
                os.remove(old_path)
        
        settings.logo_path = filename
        db.session.commit()
        
        flash('Logo berhasil diupdate!', 'success')
        
    except Exception as e:
        flash(f'Terjadi kesalahan: {str(e)}', 'error')
    
    return redirect(url_for('admin_account_settings'))

@app.route('/admin/remove-logo', methods=['POST'])
@admin_required
def admin_remove_logo():
    """Remove application logo with password protection"""
    SECRET_PASSWORD = 'bell2027'
    
    # Verifikasi password
    verified_password = request.form.get('verified_password', '')
    if verified_password != SECRET_PASSWORD:
        flash('Password tidak valid! Akses ditolak.', 'error')
        return redirect(url_for('admin_account_settings'))
    
    try:
        settings = WheelSettings.get_settings()
        
        if settings.logo_path:
            # Hapus file logo
            old_path = os.path.join(app.config['UPLOAD_FOLDER'], settings.logo_path)
            if os.path.exists(old_path):
                os.remove(old_path)
            
            # Update database
            settings.logo_path = None
            db.session.commit()
            
            flash('Logo berhasil dihapus!', 'success')
        else:
            flash('Tidak ada logo yang perlu dihapus.', 'info')
            
    except Exception as e:
        flash(f'Terjadi kesalahan: {str(e)}', 'error')
    
    return redirect(url_for('admin_account_settings'))

@app.route('/admin/update-app-text', methods=['POST'])
@admin_required
def admin_update_app_text():
    """Update application text"""
    try:
        title_text = request.form.get('title_text', '').strip()
        description_text = request.form.get('description_text', '').strip()
        
        # Validasi input
        if len(title_text) > 200:
            flash('Judul terlalu panjang! Maksimal 200 karakter.', 'error')
            return redirect(url_for('admin_account_settings'))
            
        if len(description_text) > 500:
            flash('Deskripsi terlalu panjang! Maksimal 500 karakter.', 'error')
            return redirect(url_for('admin_account_settings'))
        
        # Update database
        settings = WheelSettings.get_settings()
        settings.title_text = title_text if title_text else 'Lucky Spin Wheel'
        settings.description_text = description_text if description_text else 'Masukkan kode voucher Anda dan putar untuk memenangkan hadiah menarik!'
        
        db.session.commit()
        flash('Teks aplikasi berhasil diupdate!', 'success')
        
    except Exception as e:
        flash(f'Terjadi kesalahan: {str(e)}', 'error')
    
    return redirect(url_for('admin_account_settings'))

@app.route('/admin/settings/update', methods=['POST'])
@admin_required
def admin_update_settings():
    """Update wheel settings"""
    settings = WheelSettings.get_settings()
    
    # Update text customization
    settings.title_text = request.form.get('title_text', settings.title_text or 'Lucky Spin Wheel')
    settings.description_text = request.form.get('description_text', settings.description_text or 'Masukkan kode voucher Anda dan putar untuk memenangkan hadiah menarik!')
    settings.description_font_size = int(request.form.get('description_font_size', settings.description_font_size or 18))
    settings.description_color = request.form.get('description_color', settings.description_color or '#ffffff')
    settings.back_to_site_url = request.form.get('back_to_site_url', settings.back_to_site_url)
    settings.back_to_site_text = request.form.get('back_to_site_text', settings.back_to_site_text or 'Kembali ke Situs')
    
    # Update colors
    settings.wheel_color_1 = request.form.get('wheel_color_1', settings.wheel_color_1)
    settings.wheel_color_2 = request.form.get('wheel_color_2', settings.wheel_color_2)
    settings.text_color = request.form.get('text_color', settings.text_color)
    settings.border_color = request.form.get('border_color', settings.border_color)
    
    # Update input and button colors
    settings.input_bg_color = request.form.get('input_bg_color', settings.input_bg_color or '#ffffff')
    settings.input_text_color = request.form.get('input_text_color', settings.input_text_color or '#000000')
    settings.button_bg_color = request.form.get('button_bg_color', settings.button_bg_color or '#ffc107')
    settings.button_text_color = request.form.get('button_text_color', settings.button_text_color or '#000000')
    
    # Update popup settings
    settings.popup_enabled = bool(request.form.get('popup_enabled'))
    settings.popup_title = request.form.get('popup_title', settings.popup_title or 'Selamat!')
    settings.popup_description = request.form.get('popup_description', settings.popup_description)
    settings.popup_link_url = request.form.get('popup_link_url', settings.popup_link_url)
    settings.popup_link_text = request.form.get('popup_link_text', settings.popup_link_text or 'Kunjungi Sekarang')
    
    # Update glow settings
    settings.glow_enabled = bool(request.form.get('glow_enabled', True))
    settings.glow_color = request.form.get('glow_color', settings.glow_color or '#FF6B6B')
    settings.glow_intensity = int(request.form.get('glow_intensity', settings.glow_intensity or 50))
    
    # Update center button settings
    settings.center_button_bg_color = request.form.get('center_button_bg_color', settings.center_button_bg_color or '#ffd700')
    settings.center_button_text_color = request.form.get('center_button_text_color', settings.center_button_text_color or '#000000')
    
    # Update back button settings
    settings.back_button_bg_color = request.form.get('back_button_bg_color', settings.back_button_bg_color or '#007bff')
    settings.back_button_text_color = request.form.get('back_button_text_color', settings.back_button_text_color or '#ffffff')
    
    # Update prize border settings
    settings.prize_border_color = request.form.get('prize_border_color', settings.prize_border_color or '#ffffff')
    settings.prize_border_gradient_start = request.form.get('prize_border_gradient_start', settings.prize_border_gradient_start or '#ff0000')
    settings.prize_border_gradient_end = request.form.get('prize_border_gradient_end', settings.prize_border_gradient_end or '#9400d3')
    
    # Update container settings
    settings.container_bg_color = request.form.get('container_bg_color', settings.container_bg_color or '#1a1a2e')
    
    # Handle logo upload
    if 'logo' in request.files:
        file = request.files['logo']
        if file and file.filename and allowed_file(file.filename):
            if settings.logo_path:
                old_path = os.path.join(app.config['UPLOAD_FOLDER'], settings.logo_path)
                if os.path.exists(old_path):
                    os.remove(old_path)
            
            filename = secure_filename(file.filename)
            timestamp = str(int(datetime.now().timestamp()))
            filename = f"logo_{timestamp}_{filename}"
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            
            if not filename.lower().endswith('.svg'):
                resize_image(file_path, (200, 200))
            
            settings.logo_path = filename
    
    # Handle background upload
    if 'background' in request.files:
        file = request.files['background']
        if file and file.filename and allowed_file(file.filename):
            if settings.background_path:
                old_path = os.path.join(app.config['UPLOAD_FOLDER'], settings.background_path)
                if os.path.exists(old_path):
                    os.remove(old_path)
            
            filename = secure_filename(file.filename)
            timestamp = str(int(datetime.now().timestamp()))
            filename = f"bg_{timestamp}_{filename}"
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            
            if not filename.lower().endswith('.svg'):
                resize_image(file_path, (1200, 800))
            
            settings.background_path = filename
    
    # Handle popup image upload
    if 'popup_image' in request.files:
        file = request.files['popup_image']
        if file and file.filename and allowed_file(file.filename):
            if settings.popup_image_path:
                old_path = os.path.join(app.config['UPLOAD_FOLDER'], settings.popup_image_path)
                if os.path.exists(old_path):
                    os.remove(old_path)
            
            filename = secure_filename(file.filename)
            timestamp = str(int(datetime.now().timestamp()))
            filename = f"popup_{timestamp}_{filename}"
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            
            if not filename.lower().endswith('.svg'):
                resize_image(file_path, (400, 300))
            
            settings.popup_image_path = filename
    
    # Handle background music upload
    if 'background_music' in request.files:
        file = request.files['background_music']
        if file and file.filename and allowed_audio_file(file.filename):
            # Check file size (max 50MB)
            file.seek(0, 2)  # Seek to end of file
            file_size = file.tell()
            file.seek(0)  # Reset to beginning
            
            if file_size > 50 * 1024 * 1024:  # 50MB limit
                flash('File musik terlalu besar. Maksimum 50MB.', 'error')
            else:
                # Remove old music file if exists
                if settings.music_path:
                    old_path = os.path.join(app.config['UPLOAD_FOLDER'], settings.music_path)
                    if os.path.exists(old_path):
                        os.remove(old_path)
                
                filename = secure_filename(file.filename)
                timestamp = str(int(datetime.now().timestamp()))
                filename = f"music_{timestamp}_{filename}"
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)
                
                settings.music_path = filename
                flash('File musik berhasil diupload!', 'success')
    
    # Handle spin sound upload
    if 'spin_sound' in request.files:
        file = request.files['spin_sound']
        if file and file.filename and allowed_audio_file(file.filename):
            # Check file size (max 10MB)
            file.seek(0, 2)  # Seek to end of file
            file_size = file.tell()
            file.seek(0)  # Reset to beginning
            
            if file_size > 10 * 1024 * 1024:  # 10MB limit
                flash('File spin sound terlalu besar. Maksimum 10MB.', 'error')
            else:
                # Remove old spin sound file if exists
                if settings.spin_sound_path:
                    old_path = os.path.join(app.config['UPLOAD_FOLDER'], settings.spin_sound_path)
                    if os.path.exists(old_path):
                        os.remove(old_path)
                
                filename = secure_filename(file.filename)
                timestamp = str(int(datetime.now().timestamp()))
                filename = f"spin_{timestamp}_{filename}"
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)
                
                settings.spin_sound_path = filename
                flash('File spin sound berhasil diupload!', 'success')
    
    db.session.commit()
    flash('Settings updated successfully!', 'success')
    return redirect(url_for('admin_settings'))

@app.route('/admin/remove-image', methods=['POST'])
@admin_required
def admin_remove_image():
    """Remove uploaded images"""
    try:
        import os
        data = request.get_json()
        image_type = data.get('type')
        
        settings = WheelSettings.get_settings()
        
        if image_type == 'logo' and settings.logo_path:
            old_path = os.path.join(app.config['UPLOAD_FOLDER'], settings.logo_path)
            if os.path.exists(old_path):
                os.remove(old_path)
            settings.logo_path = None
            
        elif image_type == 'background' and settings.background_path:
            old_path = os.path.join(app.config['UPLOAD_FOLDER'], settings.background_path)
            if os.path.exists(old_path):
                os.remove(old_path)
            settings.background_path = None
            
        elif image_type == 'popup_image' and settings.popup_image_path:
            old_path = os.path.join(app.config['UPLOAD_FOLDER'], settings.popup_image_path)
            if os.path.exists(old_path):
                os.remove(old_path)
            settings.popup_image_path = None
            
        elif image_type == 'music' and settings.music_path:
            old_path = os.path.join(app.config['UPLOAD_FOLDER'], settings.music_path)
            if os.path.exists(old_path):
                os.remove(old_path)
            settings.music_path = None
            
        elif image_type == 'spin_sound' and settings.spin_sound_path:
            old_path = os.path.join(app.config['UPLOAD_FOLDER'], settings.spin_sound_path)
            if os.path.exists(old_path):
                os.remove(old_path)
            settings.spin_sound_path = None
        
        db.session.commit()
        return jsonify({'success': True, 'message': 'File removed successfully'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})

# File serving route
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    """Serve uploaded files from Object Storage with fallback"""
    try:
        # Get file content from storage (Object Storage first, then fallback)
        file_content = get_from_storage(filename)
        
        if file_content:
            # Determine MIME type based on file extension
            ext = filename.lower().split('.')[-1]
            mime_types = {
                'png': 'image/png', 'jpg': 'image/jpeg', 'jpeg': 'image/jpeg',
                'gif': 'image/gif', 'svg': 'image/svg+xml', 'webp': 'image/webp',
                'bmp': 'image/bmp', 'ico': 'image/x-icon',
                'mp3': 'audio/mpeg', 'wav': 'audio/wav', 'ogg': 'audio/ogg',
                'm4a': 'audio/mp4', 'aac': 'audio/aac', 'flac': 'audio/flac',
                'wma': 'audio/x-ms-wma', 'opus': 'audio/opus'
            }
            
            mime_type = mime_types.get(ext, 'application/octet-stream')
            
            # Return file content as HTTP response
            return Response(
                file_content,
                mimetype=mime_type,
                headers={"Cache-Control": "public, max-age=3600"}
            )
        
        # File not found anywhere
        logging.warning(f"File not found in any storage: {filename}")
        return "File not found", 404
            
    except Exception as e:
        logging.error(f"Error serving file {filename}: {e}")
        return "File not found", 404

# ====== MOBILE API ENDPOINTS ======

@app.route('/api/v1/prizes', methods=['GET'])
def api_get_prizes():
    """Get all active prizes for mobile app"""
    try:
        prizes = Prize.query.filter_by(is_active=True).all()
        prizes_data = []
        
        for prize in prizes:
            prize_dict = prize.to_dict()
            # Add full URL for icon if exists
            if prize.icon_path:
                prize_dict['icon_url'] = url_for('uploaded_file', filename=prize.icon_path, _external=True)
            prizes_data.append(prize_dict)
        
        return jsonify({
            'success': True,
            'data': prizes_data,
            'count': len(prizes_data)
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/v1/voucher/validate', methods=['POST'])
def api_validate_voucher():
    """Validate voucher code for mobile app"""
    try:
        data = request.get_json()
        voucher_code = data.get('voucher_code', '').strip().upper()
        
        if not voucher_code:
            return jsonify({
                'success': False,
                'error': 'Voucher code is required'
            }), 400
        
        voucher = Voucher.query.filter_by(code=voucher_code, is_used=False).first()
        
        if not voucher:
            return jsonify({
                'success': False,
                'error': 'Invalid or already used voucher code',
                'valid': False
            }), 400
        
        voucher_data = {
            'id': voucher.id,
            'code': voucher.code,
            'is_vip': voucher.is_vip,
            'guaranteed_prize_id': voucher.guaranteed_prize_id,
            'created_at': voucher.created_at.isoformat() if voucher.created_at else None
        }
        
        if voucher.is_vip and voucher.guaranteed_prize_id:
            prize = Prize.query.get(voucher.guaranteed_prize_id)
            if prize:
                voucher_data['guaranteed_prize'] = prize.to_dict()
        
        return jsonify({
            'success': True,
            'valid': True,
            'data': voucher_data
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/v1/spin', methods=['POST'])
def api_spin_wheel():
    """Spin wheel API for mobile app"""
    try:
        data = request.get_json()
        voucher_code = data.get('voucher_code', '').strip().upper()
        
        if not voucher_code:
            return jsonify({
                'success': False,
                'error': 'Voucher code is required'
            }), 400
        
        # Validate voucher
        voucher = Voucher.query.filter_by(code=voucher_code, is_used=False).first()
        if not voucher:
            return jsonify({
                'success': False,
                'error': 'Invalid or already used voucher code'
            }), 400
        
        # Get active prizes
        prizes = Prize.query.filter_by(is_active=True).all()
        if not prizes:
            return jsonify({
                'success': False,
                'error': 'No prizes available'
            }), 400
        
        # Check if VIP voucher with guaranteed prize
        if voucher.is_vip and voucher.guaranteed_prize_id:
            winner = Prize.query.get(voucher.guaranteed_prize_id)
            if not winner or not winner.is_active:
                return jsonify({
                    'success': False,
                    'error': 'VIP prize is no longer available'
                }), 400
        else:
            # Regular probability system
            weights = [prize.probability for prize in prizes]
            total_weight = sum(weights)
            
            if total_weight <= 0:
                return jsonify({
                    'success': False,
                    'error': 'No prizes with valid probabilities'
                }), 400
            
            # Select winner based on probability
            rand_val = random.uniform(0, total_weight)
            cumulative = 0
            winner = None
            
            for prize in prizes:
                cumulative += prize.probability
                if rand_val <= cumulative:
                    winner = prize
                    break
            
            if not winner:
                winner = prizes[-1]
        
        # Mark voucher as used
        voucher.mark_used()
        
        # Record spin result
        spin_result = SpinResult()
        spin_result.voucher_id = voucher.id
        spin_result.prize_id = winner.id
        db.session.add(spin_result)
        db.session.commit()
        
        # Calculate rotation for animation
        prize_count = len(prizes)
        segment_angle = 360 / prize_count
        winner_index = next(i for i, p in enumerate(prizes) if p.id == winner.id)
        
        base_rotations = random.randint(5, 8) * 360
        winner_angle = winner_index * segment_angle + (segment_angle / 2)
        final_angle = base_rotations + (360 - winner_angle)
        
        winner_data = winner.to_dict()
        if winner.icon_path:
            winner_data['icon_url'] = url_for('uploaded_file', filename=winner.icon_path, _external=True)
        
        return jsonify({
            'success': True,
            'data': {
                'prize': winner_data,
                'rotation': final_angle,
                'spin_id': spin_result.id,
                'voucher_code': voucher_code,
                'is_vip': voucher.is_vip
            }
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/v1/save-winner', methods=['POST'])
def api_save_winner():
    """Save winner username for mobile app"""
    try:
        data = request.get_json()
        spin_id = data.get('spin_id')
        username = data.get('username', '').strip()
        
        if not spin_id or not username:
            return jsonify({
                'success': False,
                'error': 'Spin ID and username are required'
            }), 400
        
        spin_result = SpinResult.query.get(spin_id)
        if not spin_result:
            return jsonify({
                'success': False,
                'error': 'Spin result not found'
            }), 404
        
        spin_result.username = username
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Winner saved successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/v1/winners', methods=['GET'])
def api_get_winners():
    """Get recent winners for mobile app"""
    try:
        from sqlalchemy import desc
        limit = request.args.get('limit', 10, type=int)
        
        winners = db.session.query(SpinResult, Prize, Voucher).join(
            Prize, SpinResult.prize_id == Prize.id
        ).join(
            Voucher, SpinResult.voucher_id == Voucher.id
        ).order_by(desc(SpinResult.spun_at)).limit(limit).all()
        
        winners_data = []
        for spin_result, prize, voucher in winners:
            winner_dict = {
                'id': spin_result.id,
                'username': spin_result.username,
                'prize': prize.to_dict(),
                'voucher_code': voucher.code,
                'is_vip': voucher.is_vip,
                'spun_at': spin_result.spun_at.isoformat() if spin_result.spun_at else None
            }
            
            if prize.icon_path:
                winner_dict['prize']['icon_url'] = url_for('uploaded_file', filename=prize.icon_path, _external=True)
            
            winners_data.append(winner_dict)
        
        return jsonify({
            'success': True,
            'data': winners_data,
            'count': len(winners_data)
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/v1/settings', methods=['GET'])
def api_get_settings():
    """Get wheel settings for mobile app"""
    try:
        settings = WheelSettings.get_settings()
        
        settings_data = {
            'wheel_title': settings.wheel_title,
            'winning_message': settings.winning_message,
            'popup_title': settings.popup_title,
            'popup_message': settings.popup_message,
            'wheel_colors': settings.wheel_colors,
            'text_color': settings.text_color,
            'spin_duration': settings.spin_duration,
            'auto_spin': settings.auto_spin,
            'show_confetti': settings.show_confetti,
            'show_winner_popup': settings.show_winner_popup,
            'enable_sound': settings.enable_sound,
            'created_at': settings.created_at.isoformat() if settings.created_at else None,
            'updated_at': settings.updated_at.isoformat() if settings.updated_at else None
        }
        
        # Add URLs for assets
        if settings.logo_path:
            settings_data['logo_url'] = url_for('uploaded_file', filename=settings.logo_path, _external=True)
        
        if settings.background_path:
            settings_data['background_url'] = url_for('uploaded_file', filename=settings.background_path, _external=True)
        
        if settings.popup_image_path:
            settings_data['popup_image_url'] = url_for('uploaded_file', filename=settings.popup_image_path, _external=True)
        
        if settings.music_path:
            settings_data['music_url'] = url_for('uploaded_file', filename=settings.music_path, _external=True)
        
        return jsonify({
            'success': True,
            'data': settings_data
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/v1/stats', methods=['GET'])
def api_get_stats():
    """Get application statistics for mobile app"""
    try:
        stats = {
            'total_prizes': Prize.query.filter_by(is_active=True).count(),
            'total_vouchers': Voucher.query.count(),
            'active_vouchers': Voucher.query.filter_by(is_used=False).count(),
            'used_vouchers': Voucher.query.filter_by(is_used=True).count(),
            'vip_vouchers': Voucher.query.filter_by(is_vip=True, is_used=False).count(),
            'total_spins': SpinResult.query.count(),
            'recent_winners': SpinResult.query.filter(SpinResult.username.isnot(None)).count()
        }
        
        return jsonify({
            'success': True,
            'data': stats
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# Error handlers
@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('500.html'), 500
