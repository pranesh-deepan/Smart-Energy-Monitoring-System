from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models import db, User, ElectricityBill, BlynkDevice, assign_badges_for_user, get_user_badges, award_signup_badge
import requests

# --- Firebase Admin SDK for Push Notifications ---
import os
import firebase_admin
from firebase_admin import credentials, messaging

FIREBASE_CRED_PATH = os.environ.get('FIREBASE_CRED_PATH', 'firebase-adminsdk.json')
if not firebase_admin._apps:
    if os.path.exists(FIREBASE_CRED_PATH):
        cred = credentials.Certificate(FIREBASE_CRED_PATH)
        firebase_admin.initialize_app(cred)
    else:
        print('WARNING: Firebase credential file not found, push notifications will not work.')

def send_push_notification(token, title, body):
    if not token or not firebase_admin._apps:
        print('No FCM token or Firebase not initialized')
        return
    try:
        message = messaging.Message(
            notification=messaging.Notification(
                title=title,
                body=body
            ),
            token=token
        )
        response = messaging.send(message)
        print('Push notification sent:', response)
    except Exception as e:
        print('Error sending push notification:', e)

# Create a blueprint for electricity-related routes
electricity_bp = Blueprint('electricity', __name__)

@electricity_bp.route('/set_v2_limit', methods=['POST'])
@login_required
def set_v2_limit():
    try:
        v2_limit = float(request.form.get('v2_limit'))
        current_user.v2_limit = v2_limit
        db.session.commit()
        flash(f'V2 limit set to {v2_limit} W', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error setting V2 limit: {e}', 'danger')
    return redirect(url_for('electricity.electricity_usage'))

@electricity_bp.route('/electricity_usage')
@login_required
def electricity_usage():
    award_signup_badge(current_user)
    assign_badges_for_user(current_user)
    # DEBUG: Force badges to a test value
    badges = ["Welcome Aboard", "Energy Saver"]
    # Ensure 'Welcome Aboard' badge is always shown
    if 'Welcome Aboard' not in badges:
        badges.append('Welcome Aboard')
    # Fetch any other required data for the template (e.g., usage, advice)
    return render_template('electricity_usage.html', badges=badges)

# AJAX endpoint for real-time usage data (POST)
@electricity_bp.route('/electricity-usage', methods=['GET', 'POST'])
@login_required
def electricity_usage_data():
    blynk_devices = BlynkDevice.query.filter_by(user_id=current_user.id).all()
    selected_device_id = request.args.get('selected_device') or request.form.get('selected_device')
    blynk_data = None
    limit_exceeded = False

    if selected_device_id:
        selected_device = BlynkDevice.query.get(selected_device_id)
        if selected_device:
            blynk_data = selected_device.fetch_blynk_data()
            # Check V2 pin (power) vs user limit
            v2_value = blynk_data.get('power')
            user_limit = current_user.v2_limit
            if user_limit is not None and v2_value is not None and float(v2_value) > float(user_limit):
                limit_exceeded = True
                # Push notification if user has FCM token
                if current_user.fcm_token:
                    send_push_notification(
                        current_user.fcm_token,
                        'SmartWatt Alert',
                        f'Your device power (V2) exceeded your set limit of {user_limit} W!'
                    )

    # If it's an AJAX request, return JSON
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.method == 'POST':
        resp = blynk_data or {}
        resp['limit_exceeded'] = limit_exceeded
        return jsonify(resp)

    return render_template('electricity_usage.html', 
                           blynk_devices=blynk_devices, 
                           selected_device_id=int(selected_device_id) if selected_device_id and str(selected_device_id).isdigit() else None,
                           blynk_data=blynk_data)

@electricity_bp.route('/electricity_bills')
@login_required
def electricity_bills():
    award_signup_badge(current_user)
    assign_badges_for_user(current_user)
    """
    Electricity bills page with cost details and account information
    
    Features:
    1. Show user's account number
    2. Display daily bill history
    3. Placeholders for future preference and messaging modules
    """
    # Fetch user's electricity bills
    bills = ElectricityBill.query.filter_by(user_id=current_user.id).order_by(ElectricityBill.date.desc()).all()
    
    # Prepare bill data for template
    bill_data = []
    for bill in bills:
        bill_data.append({
            'date': bill.date,
            'total_energy': bill.total_energy,
            'total_cost': bill.total_cost,
            'co2_emission': bill.co2_emission,
            'cost_breakdown': bill.cost_breakdown
        })
    
    solar_rating = getattr(current_user, 'solar_rating', None)
    # Render electricity bills template
    return render_template(
        'electricity_bills.html', 
        solar_rating=solar_rating,
        account_number=current_user.account_number,
        bills=bill_data,
        preferences_module=None,  # Placeholder for future preferences module
        messaging_module=None     # Placeholder for future messaging module
    )

# Device ON/OFF API
@electricity_bp.route('/api/device_switch', methods=['POST'])
def device_switch():
    data = request.get_json()
    state = data.get('state')
    if state not in [0, 1]:
        return '', 204
    token = "sGa2Ws1F_FjLjdZYWB-zk4Wf2kjCozkG"
    url = f"https://blr1.blynk.cloud/external/api/update?token={token}&V4={state}"
    requests.get(url, timeout=5)
    return '', 204

@electricity_bp.route('/api/device_state', methods=['GET'])
def device_state():
    token = "sGa2Ws1F_FjLjdZYWB-zk4Wf2kjCozkG"
    url = f"https://blr1.blynk.cloud/external/api/get?token={token}&V4"
    try:
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            return jsonify({'state': int(resp.text.strip())})
        else:
            return jsonify({'state': None}), 500
    except Exception:
        return jsonify({'state': None}), 500

# Voltage/Current API
@electricity_bp.route('/api/voltage_current', methods=['GET'])
def voltage_current():
    device_id = request.args.get('device_id')
    device = BlynkDevice.query.get(device_id)
    if not device:
        return jsonify({"voltage": None, "current": None}), 404
    token = device.auth_token
    url_v0 = f"https://blr1.blynk.cloud/external/api/get?token={token}&V0"
    url_v1 = f"https://blr1.blynk.cloud/external/api/get?token={token}&V1"
    try:
        resp_v0 = requests.get(url_v0, timeout=5)
        resp_v1 = requests.get(url_v1, timeout=5)
        voltage = float(resp_v0.text.strip()) if resp_v0.status_code == 200 else None
        current = float(resp_v1.text.strip()) if resp_v1.status_code == 200 else None
        return jsonify({"voltage": voltage, "current": current})
    except Exception:
        return jsonify({"voltage": None, "current": None}), 500

# Power advice logic

def get_power_advice(power):
    if power > 500:
        return {
            "status": "CRITICAL",
            "message": "⚠ Very high usage! Turn off heavy appliances like AC, oven, or washing machine."
        }
    elif power > 300:
        return {
            "status": "HIGH",
            "message": "🔍 High usage detected. Consider reducing usage—check water heater, fridge, or motor."
        }
    elif power > 100:
        return {
            "status": "MEDIUM",
            "message": "✅ Moderate usage. Consider turning off unused lights or fans."
        }
    else:
        return {
            "status": "LOW",
            "message": "🟢 Low power usage. All systems running efficiently."
        }

from requests.exceptions import Timeout, ConnectionError

@electricity_bp.route('/api/power_advice', methods=['GET'])
def power_advice():
    device_id = request.args.get('device_id')
    device = None
    if device_id:
        device = BlynkDevice.query.get(device_id)
    if not device:
        # Fallback to first device for the current user if available
        if current_user.is_authenticated:
            device = BlynkDevice.query.filter_by(user_id=current_user.id).first()
    if not device:
        return jsonify({"status": "UNKNOWN", "message": "No device found for power advice.", "power": None}), 404
    token = device.auth_token
    url = f"https://blr1.blynk.cloud/external/api/get?token={token}&V2"  # V2 is power
    try:
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            try:
                power = float(resp.text.strip())
            except Exception:
                power = 0.0
            advice = get_power_advice(power)
            advice["power"] = power
            return jsonify(advice)
        else:
            return jsonify({"status": "UNKNOWN", "message": "Could not fetch power data from cloud.", "power": None}), 500
    except Timeout:
        return jsonify({"status": "UNKNOWN", "message": "Blynk cloud timed out. Please try again later.", "power": None}), 504
    except ConnectionError:
        return jsonify({"status": "UNKNOWN", "message": "Cannot connect to Blynk cloud. Check your network.", "power": None}), 502
    except Exception:
        return jsonify({"status": "UNKNOWN", "message": "An unexpected error occurred while fetching power advice.", "power": None}), 500

@electricity_bp.route('/api/delete_device/<int:device_id>', methods=['POST'])
def delete_device(device_id):
    device = BlynkDevice.query.get(device_id)
    if not device:
        return {'success': False, 'message': 'Device not found'}, 404
    # Delete all related logs first
    for log in device.data_logs:
        db.session.delete(log)
    db.session.delete(device)
    db.session.commit()
    return {'success': True, 'message': 'Device removed'}

# Placeholder routes for future modules
@electricity_bp.route('/preferences')
@login_required
def preferences():
    """Placeholder for future preferences module"""
    return "Preferences module coming soon!"

@electricity_bp.route('/messages')
@login_required
def messages():
    """Placeholder for future messaging module"""
    return "Messaging module coming soon!"
