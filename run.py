import os
import smtplib
from email.message import EmailMessage
from flask import Flask, render_template, redirect, url_for, flash, request, jsonify, send_file
from flask_bootstrap import Bootstrap5
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from dotenv import load_dotenv
from models import db, User, BlynkDevice, ElectricityBill
from forms import LoginForm, RegistrationForm, BlynkDeviceForm
from werkzeug.security import check_password_hash
from datetime import datetime
from routes import electricity_bp

# Load environment variables
load_dotenv()

# Create and configure Flask app
app = Flask(__name__)
Bootstrap5(app)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key')  # Use a secure key in production
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///electricity_management.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Register blueprints
app.register_blueprint(electricity_bp, url_prefix='/electricity')

# Email config (for demo, set directly; for prod, use env vars)
EMAIL_ADDRESS = os.getenv('EMAIL_ADDRESS', 'electricitycommissionofindia@gmail.com')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD', 'tszyszoklxwssjma')

def send_bill_email(to_email, subject, html_content):
    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = EMAIL_ADDRESS
    msg['To'] = to_email
    msg.set_content('This email requires an HTML-compatible client.')
    msg.add_alternative(html_content, subtype='html')
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        smtp.send_message(msg)
# Only send to the user's email, not the commission


# Initialize extensions
db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Create database tables
with app.app_context():
    db.create_all()
    # Award Welcome Aboard badge to all users who don't have it
    from models import User, award_signup_badge
    for user in User.query.all():
        award_signup_badge(user)

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    print('Signup route accessed')  # Debug
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    form = RegistrationForm()
    print(f'Form created: {form}')  # Debug
    if form.validate_on_submit():
        print('Form submitted')  # Debug
        # Check if user already exists
        existing_user = User.query.filter_by(email=form.email.data).first()
        if existing_user:
            flash('Email already registered. Please use a different email.', 'danger')
            return render_template('signup.html', form=form)
        
        # Create new user
        user = User(
            username=form.username.data, 
            email=form.email.data
        )
        user.set_password(form.password.data)
        
        # Handle profile picture
        if form.profile_picture.data:
            picture_file = save_picture(form.profile_picture.data)
            user.profile_picture = picture_file
        try:
            db.session.add(user)
            db.session.commit()
            from models import award_signup_badge
            award_signup_badge(user)
            flash('Account created successfully! Please log in.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating account: {str(e)}', 'danger')
    # Always render the signup form if not redirected
    return render_template('signup.html', form=form)

def save_picture(form_picture):
    import os
    from werkzeug.utils import secure_filename
    import uuid
    upload_folder = os.path.join('static', 'profile_pictures')
    os.makedirs(upload_folder, exist_ok=True)
    ext = os.path.splitext(form_picture.filename)[1]
    unique_filename = f"{uuid.uuid4().hex}{ext}"
    file_path = os.path.join(upload_folder, unique_filename)
    form_picture.save(file_path)
    return f"profile_pictures/{unique_filename}"



@app.route('/login', methods=['GET', 'POST'])
def login():
    print('Login route accessed')  # Debug
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    form = LoginForm()
    print(f'Form created: {form}')  # Debug
    if form.validate_on_submit():
        print('Form submitted')  # Debug
        user = User.query.filter_by(email=form.email.data).first()
        if user and user.check_password(form.password.data):
            # Update last login time
            user.last_login = datetime.utcnow()
            
            try:
                db.session.add(user)
                db.session.commit()
                
                login_user(user, remember=form.remember.data)
                flash('Login successful!', 'success')
                return redirect(url_for('dashboard'))
            except Exception as e:
                db.session.rollback()
                flash(f'Login error: {str(e)}', 'danger')
        else:
            flash('Invalid email or password', 'danger')
    
    print('Rendering template with form')  # Debug
    return render_template('login.html', form=form)

@app.route('/update-profile-picture', methods=['POST'])
@login_required
def update_profile_picture():
    if 'profile_picture' not in request.files:
        flash('No file part', 'danger')
        return redirect(url_for('dashboard'))
    file = request.files['profile_picture']
    if file.filename == '':
        flash('No selected file', 'danger')
        return redirect(url_for('dashboard'))
    if file:
        picture_file = save_picture(file)
        current_user.profile_picture = picture_file
        db.session.commit()
        flash('Profile picture updated!', 'success')
    return redirect(url_for('dashboard'))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('home'))

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html', account_number=current_user.account_number)

def save_picture(form_picture):
    # Generate a random filename
    random_hex = os.urandom(8).hex()
    _, f_ext = os.path.splitext(form_picture.filename)
    picture_fn = random_hex + f_ext
    picture_path = os.path.join(app.root_path, 'static/profile_pictures', picture_fn)
    
    # Ensure the directory exists
    os.makedirs(os.path.join(app.root_path, 'static/profile_pictures'), exist_ok=True)
    
    # Save the picture
    form_picture.save(picture_path)
    return os.path.join('profile_pictures', picture_fn).replace('\\', '/')

@app.route('/electricity-bills')
@login_required
def electricity_bills():
    bills = ElectricityBill.query.filter_by(user_id=current_user.id).all()
    return render_template('electricity_bills.html', bills=bills, account_number=current_user.account_number)

@app.route('/devices', methods=['GET', 'POST'])
@login_required
def devices():
    form = BlynkDeviceForm()
    if request.method == 'POST' and 'solar_rating' in request.form:
        try:
            rating = float(request.form['solar_rating'])
            current_user.solar_rating = rating
            db.session.commit()
            flash('Solar panel rating saved!', 'success')
        except Exception:
            flash('Invalid input for solar panel rating.', 'danger')
        return redirect(url_for('devices'))
    blynk_devices = BlynkDevice.query.filter_by(user_id=current_user.id).all()
    solar_rating = getattr(current_user, 'solar_rating', None)
    return render_template('devices.html', blynk_device_form=form, blynk_devices=blynk_devices, solar_rating=solar_rating)


@app.route('/remove-device/<int:device_id>', methods=['POST'])
@login_required
def remove_device(device_id):
    device = BlynkDevice.query.get_or_404(device_id)
    if device.user_id != current_user.id:
        flash('Unauthorized to remove this device.', 'danger')
        return redirect(url_for('devices'))
    db.session.delete(device)
    db.session.commit()
    flash('Device removed successfully.', 'success')
    return redirect(url_for('devices'))

@app.route('/register-blynk-device', methods=['GET', 'POST'])
@login_required
def register_blynk_device():
    form = BlynkDeviceForm()
    blynk_devices = BlynkDevice.query.filter_by(user_id=current_user.id).all()
    if form.validate_on_submit():
        new_device = BlynkDevice(
            user_id=current_user.id,
            device_name=form.device_name.data,
            auth_token=form.auth_token.data,
            virtual_pin_voltage=form.virtual_pin_voltage.data,
            virtual_pin_current=form.virtual_pin_current.data,
            virtual_pin_power=form.virtual_pin_power.data,
            virtual_pin_energy=form.virtual_pin_energy.data
        )
        db.session.add(new_device)
        db.session.commit()
        flash('Blynk device registered successfully!', 'success')
        return redirect(url_for('devices'))
    else:
        # If form is invalid, render devices.html with errors and existing devices
        flash('Please correct the errors below and try again.', 'danger')
        return render_template('devices.html', blynk_device_form=form, blynk_devices=blynk_devices)

@app.route('/electricity-usage', methods=['GET', 'POST'])
@login_required
def electricity_usage():
    blynk_devices = BlynkDevice.query.filter_by(user_id=current_user.id).all()
    selected_device_id = request.args.get('selected_device') or request.form.get('selected_device')
    blynk_data = None

    if selected_device_id:
        selected_device = BlynkDevice.query.get(selected_device_id)
        if selected_device:
            blynk_data = selected_device.fetch_blynk_data()

    # If it's an AJAX request, return JSON
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.method == 'POST':
        return jsonify(blynk_data or {})

    return render_template('electricity_usage.html', 
                           blynk_devices=blynk_devices, 
                           selected_device_id=int(selected_device_id) if selected_device_id and str(selected_device_id).isdigit() else None,
                           blynk_data=blynk_data)

@app.route('/api/device-hourly')
@login_required
def api_device_hourly():
    device_id = request.args.get('device_id')
    if not device_id:
        return jsonify({'error': 'Missing device_id'}), 400
    from models import BlynkDataLog
    import datetime
    now = datetime.datetime.utcnow()
    start = now - datetime.timedelta(hours=24)
    logs = BlynkDataLog.query.filter_by(device_id=device_id).filter(BlynkDataLog.timestamp >= start).order_by(BlynkDataLog.timestamp).all()
    # Group by hour
    hourly = {}
    for log in logs:
        hour = log.timestamp.replace(minute=0, second=0, microsecond=0)
        if hour not in hourly:
            hourly[hour] = {'power': [], 'energy': []}
        hourly[hour]['power'].append(log.power or 0)
        hourly[hour]['energy'].append(log.energy or 0)
    result = []
    for hour, vals in sorted(hourly.items()):
        result.append({
            'label': hour.strftime('%Y-%m-%d %H:%M'),
            'power': sum(vals['power'])/len(vals['power']) if vals['power'] else 0,
            'energy': sum(vals['energy'])/len(vals['energy']) if vals['energy'] else 0
        })
    return jsonify(result)

@app.route('/api/device-weekly')
@login_required
def api_device_weekly():
    device_id = request.args.get('device_id')
    if not device_id:
        return jsonify({'error': 'Missing device_id'}), 400
    from models import BlynkDataLog
    import datetime
    now = datetime.datetime.utcnow()
    start = now - datetime.timedelta(days=7)
    logs = BlynkDataLog.query.filter_by(device_id=device_id).filter(BlynkDataLog.timestamp >= start).order_by(BlynkDataLog.timestamp).all()
    # Group by day
    daily = {}
    for log in logs:
        day = log.timestamp.date()
        if day not in daily:
            daily[day] = {'power': [], 'energy': []}
        daily[day]['power'].append(log.power or 0)
        daily[day]['energy'].append(log.energy or 0)
    result = []
    for day, vals in sorted(daily.items()):
        result.append({
            'label': day.strftime('%Y-%m-%d'),
            'power': sum(vals['power'])/len(vals['power']) if vals['power'] else 0,
            'energy': sum(vals['energy'])/len(vals['energy']) if vals['energy'] else 0
        })
    return jsonify(result)

@app.route('/api/device-monthly')
@login_required
def api_device_monthly():
    device_id = request.args.get('device_id')
    if not device_id:
        return jsonify({'error': 'Missing device_id'}), 400
    from models import BlynkDataLog
    import datetime
    now = datetime.datetime.utcnow()
    start = now - datetime.timedelta(days=30)
    logs = BlynkDataLog.query.filter_by(device_id=device_id).filter(BlynkDataLog.timestamp >= start).order_by(BlynkDataLog.timestamp).all()
    # Group by day
    daily = {}
    for log in logs:
        day = log.timestamp.date()
        if day not in daily:
            daily[day] = {'power': [], 'energy': []}
        daily[day]['power'].append(log.power or 0)
        daily[day]['energy'].append(log.energy or 0)
    result = []
    for day, vals in sorted(daily.items()):
        result.append({
            'label': day.strftime('%Y-%m-%d'),
            'power': sum(vals['power'])/len(vals['power']) if vals['power'] else 0,
            'energy': sum(vals['energy'])/len(vals['energy']) if vals['energy'] else 0
        })
    return jsonify(result)


@app.route('/download-logs/<int:device_id>')
@login_required
def download_logs(device_id):
    device = BlynkDevice.query.get(device_id)
    if not device:
        flash('Device not found.', 'danger')
        return redirect(url_for('electricity_usage'))
    # Use export_logs_to_csv to generate CSV
    log_file = device.export_logs_to_csv() if hasattr(device, 'export_logs_to_csv') else None
    import os
    if not log_file or not os.path.exists(log_file):
        flash('No logs found for this device.', 'warning')
        return redirect(url_for('electricity_usage', selected_device=device_id))
    return send_file(log_file, as_attachment=True)

@app.route('/remove_solar_panel', methods=['POST'])
@login_required
def remove_solar_panel():
    current_user.solar_rating = None
    db.session.commit()
    flash('Solar panel removed!', 'info')
    return redirect(url_for('devices'))

@app.route('/add_test_bill')
@login_required
def add_test_bill():
    from datetime import datetime
    # Add a test bill for the current user
    bill = ElectricityBill(
        user_id=current_user.id,
        date=datetime.now().date(),
        total_energy=123.4,
        total_cost=567.8,
        co2_emission=98.7,
        cost_breakdown=None
    )
    db.session.add(bill)
    db.session.commit()
    flash('Test bill added!', 'success')
    return redirect(url_for('electricity_bills'))

@app.route('/add_screenshot_test_bill')
@login_required
def add_screenshot_test_bill():
    from datetime import datetime
    # Data from screenshot: Consumed=700Wh, Solar=50Wh, Grid=650Wh, Cost=3.59, Solar offset=0.47, Final=3.12, CO2=0.57kg, CO2 saved=0.04kg
    bill = ElectricityBill(
        user_id=current_user.id,
        date=datetime.now().date(),
        total_energy=0.7,  # 700 Wh = 0.7 kWh
        total_cost=3.59,
        co2_emission=0.57,
        cost_breakdown=None
    )
    db.session.add(bill)
    db.session.commit()
    flash('Screenshot-style test bill added!', 'success')
    return redirect(url_for('electricity_bills'))

@app.route('/test_push')
@login_required
def test_push():
    import os
    import firebase_admin
    from firebase_admin import credentials, messaging
    # Only initialize once
    if not firebase_admin._apps:
        cred_path = os.environ.get('FIREBASE_CRED_PATH')
        if not cred_path or not os.path.exists(cred_path):
            flash('Firebase credentials not found. Set FIREBASE_CRED_PATH.', 'danger')
            return redirect(url_for('electricity_bills'))
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred)
    # You must provide your device's FCM token here
    registration_token = os.environ.get('TEST_FCM_TOKEN')
    if not registration_token:
        flash('Set TEST_FCM_TOKEN env variable with your device FCM token.', 'danger')
        return redirect(url_for('electricity_bills'))
    message = messaging.Message(
        notification=messaging.Notification(
            title='Test Notification',
            body='This is a test push notification from your Flask app!',
        ),
        token=registration_token,
    )
    try:
        response = messaging.send(message)
        flash('Push notification sent! Response: ' + response, 'success')
    except Exception as e:
        flash('Failed to send push notification: ' + str(e), 'danger')
    return redirect(url_for('electricity_bills'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
