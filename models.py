import os
import uuid
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
import requests
import csv

db = SQLAlchemy()

class ElectricityBill(db.Model):
    """Model to track daily electricity bills and costs"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date = db.Column(db.Date, nullable=False, index=True)
    total_energy = db.Column(db.Float, nullable=False)
    total_cost = db.Column(db.Float, nullable=False)
    co2_emission = db.Column(db.Float, nullable=False)
    cost_breakdown = db.Column(db.JSON, nullable=True)  # Store slab-wise cost breakdown
    
    user = db.relationship('User', backref=db.backref('electricity_bills', lazy='dynamic'))
    
    @classmethod
    def create_bill(cls, user, total_energy, total_cost, co2_emission, cost_breakdown):
        """Create a new electricity bill entry"""
        bill = cls(
            user_id=user.id,
            date=datetime.now().date(),
            total_energy=total_energy,
            total_cost=total_cost,
            co2_emission=co2_emission,
            cost_breakdown=cost_breakdown
        )
        db.session.add(bill)
        db.session.commit()
        return bill

class BlynkDataLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.Integer, db.ForeignKey('blynk_device.id'), nullable=False)
    voltage = db.Column(db.Float, nullable=True)
    current = db.Column(db.Float, nullable=True)
    power = db.Column(db.Float, nullable=True)
    energy = db.Column(db.Float, nullable=True)
    cumulative_energy = db.Column(db.Float, default=0.0)  # New column to accumulate energy
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    device = db.relationship('BlynkDevice', backref=db.backref('data_logs', lazy=True))

    def update_cumulative_energy(self, new_energy):
        """Add new energy to cumulative total"""
        self.cumulative_energy += new_energy

def generate_account_number():
    """Generate a unique 10-digit account number."""
    return str(uuid.uuid4().int)[:10]

def generate_profile_picture_filename(username, file):
    """Generate a unique filename for profile picture."""
    ext = os.path.splitext(file.filename)[1]
    unique_filename = f"{username}_{uuid.uuid4()}{ext}"
    return secure_filename(unique_filename)

class User(UserMixin, db.Model):
    solar_rating = db.Column(db.Float, nullable=True)  # Solar panel rating (kW)
    solar_generation = db.Column(db.Float, nullable=True)  # Estimated daily solar generation (kWh)
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    account_number = db.Column(db.String(10), unique=True, nullable=False, default=generate_account_number)
    profile_picture = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)
    v2_limit = db.Column(db.Float, nullable=True)  # User-settable V2 pin limit
    fcm_token = db.Column(db.String(255), nullable=True)  # For push notifications
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def set_profile_picture(self, file):
        """Save profile picture and update user record."""
        if file:
            # Ensure profile pictures directory exists
            upload_folder = os.path.join('static', 'profile_pictures')
            os.makedirs(upload_folder, exist_ok=True)
            
            # Generate unique filename
            filename = generate_profile_picture_filename(self.username, file)
            filepath = os.path.join(upload_folder, filename)
            
            # Save file
            file.save(filepath)
            
            # Update user's profile picture path
            self.profile_picture = os.path.join('profile_pictures', filename)
    
    def __repr__(self):
        return f'<User {self.username}>'

class BlynkDevice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    device_name = db.Column(db.String(50), nullable=False)
    auth_token = db.Column(db.String(255), nullable=False)
    virtual_pin_voltage = db.Column(db.String(10), nullable=False)
    virtual_pin_current = db.Column(db.String(10), nullable=False)
    virtual_pin_power = db.Column(db.String(10), nullable=False)
    virtual_pin_energy = db.Column(db.String(10), nullable=False)
    user = db.relationship('User', backref=db.backref('blynk_devices', lazy=True))

    def fetch_blynk_data(self, interval_minutes=5):
        """Fetch Blynk data and accumulate energy
        
        :param interval_minutes: Time interval for energy calculation (default 5 minutes)
        """
        base_url = 'https://blr1.blynk.cloud/external/api/get'
        data = {}
        try:
            # Fetch voltage
            voltage_response = requests.get(f'{base_url}?token={self.auth_token}&{self.virtual_pin_voltage}')
            data['voltage'] = float(voltage_response.text) if voltage_response.status_code == 200 else None

            # Fetch current
            current_response = requests.get(f'{base_url}?token={self.auth_token}&{self.virtual_pin_current}')
            data['current'] = float(current_response.text) if current_response.status_code == 200 else None

            # Fetch power
            power_response = requests.get(f'{base_url}?token={self.auth_token}&{self.virtual_pin_power}')
            data['power'] = float(power_response.text) if power_response.status_code == 200 else None

            # Fetch energy
            energy_response = requests.get(f'{base_url}?token={self.auth_token}&{self.virtual_pin_energy}')
            data['energy'] = float(energy_response.text) if energy_response.status_code == 200 else None

            # Calculate energy based on interval
            if data['power'] is not None:
                # Convert power to energy: Power (W) * Time (hours)
                interval_hours = interval_minutes / 60
                calculated_energy = data['power'] * interval_hours / 1000  # Convert to kWh
                data['calculated_energy'] = calculated_energy

            # Log the data
            log_entry = self.log_data(data)

            # Update cumulative energy
            # Prefer calculated energy if available, else use V3 energy
            energy_to_add = data.get('calculated_energy', data.get('energy', 0))
            if energy_to_add is not None and log_entry:
                log_entry.update_cumulative_energy(energy_to_add)
                db.session.commit()

        except Exception as e:
            print(f"Error fetching Blynk data: {e}")
        return data

    def get_cumulative_energy(self):
        """Retrieve the latest cumulative energy for this device"""
        latest_log = BlynkDataLog.query.filter_by(device_id=self.id).order_by(BlynkDataLog.timestamp.desc()).first()
        return latest_log.cumulative_energy if latest_log else 0.0

    def log_data(self, data):
        from run import db
        from models import BlynkDataLog

        # Create a new log entry
        log_entry = BlynkDataLog(
            device_id=self.id,
            voltage=data.get('voltage'),
            current=data.get('current'),
            power=data.get('power'),
            energy=data.get('energy')
        )
        db.session.add(log_entry)
        db.session.commit()
        return log_entry

    def export_logs_to_csv(self):
        logs = BlynkDataLog.query.filter_by(device_id=self.id).order_by(BlynkDataLog.timestamp).all()
        
        # Ensure logs directory exists
        os.makedirs('logs', exist_ok=True)
        
        # Create filename with device name and timestamp
        filename = f'logs/{self.device_name}_logs_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        
        with open(filename, 'w', newline='') as csvfile:
            fieldnames = ['timestamp', 'voltage', 'current', 'power', 'energy']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            writer.writeheader()
            for log in logs:
                writer.writerow({
                    'timestamp': log.timestamp,
                    'voltage': log.voltage,
                    'current': log.current,
                    'power': log.power,
                    'energy': log.energy
                })
        
        return filename

class UserBadge(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    badge_name = db.Column(db.String(64), nullable=False)
    badge_icon = db.Column(db.String(32), nullable=False)  # e.g., 'star-fill', 'calendar-check', 'moon-stars'
    badge_color = db.Column(db.String(32), nullable=False) # e.g., 'warning', 'info', 'dark'
    description = db.Column(db.String(128), nullable=False)
    awarded_on = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('badges', lazy=True))


def get_user_badges(user_id):
    return UserBadge.query.filter_by(user_id=user_id).all()

# Utility: assign badges based on energy usage patterns
from sqlalchemy.sql import func

def award_signup_badge(user):
    try:
        print(f"[DEBUG] Checking Welcome Aboard badge for user {user.id} ({getattr(user, 'username', None)})")
        badge = UserBadge.query.filter_by(user_id=user.id, badge_name='Welcome Aboard').first()
        if not badge:
            print(f"[DEBUG] Awarding Welcome Aboard badge to user {user.id} ({getattr(user, 'username', None)})")
            badge = UserBadge(
                user_id=user.id,
                badge_name='Welcome Aboard',
                badge_icon='person-plus',
                badge_color='primary',
                description='🎉 Welcome Aboard! Thanks for joining our energy-saving community.'
            )
            db.session.add(badge)
            db.session.commit()
        else:
            print(f"[DEBUG] User {user.id} already has the Welcome Aboard badge.")
    except Exception as e:
        print(f"[ERROR] Failed to award Welcome Aboard badge: {e}")

def assign_badges_for_user(user):
    """
    Assign badges to user based on energy usage patterns. This is a basic version; expand as needed.
    """
    from models import BlynkDataLog, BlynkDevice
    # Device Linker: Linked at least one remote device
    if BlynkDevice.query.filter_by(user_id=user.id).count() > 0:
        if not UserBadge.query.filter_by(user_id=user.id, badge_name='Device Linker').first():
            badge = UserBadge(
                user_id=user.id,
                badge_name='Device Linker',
                badge_icon='link-45deg',
                badge_color='success',
                description='🌐 Gorgeous! Linked your first remote device. Unlock the power of smart energy!'
            )
            db.session.add(badge)

    # Example: Gold Saver badge for low monthly energy usage
    month_ago = datetime.utcnow() - timedelta(days=30)
    # Calculate monthly usage for all devices owned by this user
    month_usage = (
        db.session.query(func.sum(BlynkDataLog.energy))
        .join(BlynkDevice, BlynkDataLog.device_id == BlynkDevice.id)
        .filter(BlynkDevice.user_id == user.id, BlynkDataLog.timestamp >= month_ago)
        .scalar() or 0
    )
    if month_usage < 50:  # Example threshold
        if not UserBadge.query.filter_by(user_id=user.id, badge_name='Gold Saver').first():
            badge = UserBadge(user_id=user.id, badge_name='Gold Saver', badge_icon='star-fill', badge_color='warning', description='🏅 Gold Saver: You achieved outstanding energy savings this month!')
            db.session.add(badge)
    # Consistent User: Used platform every day for 30 days
    # (Check UserActivity or login dates)
    # Night Owl: Most energy saved during night hours
    # (Analyze BlynkDataLog timestamps)
    db.session.commit()
