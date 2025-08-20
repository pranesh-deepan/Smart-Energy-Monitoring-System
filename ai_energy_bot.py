import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import time

# === CONFIGURATION ===
BLYNK_TOKEN = "apZH1A-XPrxZ3yuxgINdpOhVw1x-n6yL"  # Replace with your Blynk token
VIRTUAL_PIN_POWER = "v2"          # Power usage input
VIRTUAL_PIN_CONTROL = "v3"        # Control output to device (e.g., relay)
VIRTUAL_PIN_TEXT_INPUT = "v6"     # User text input pin (OFF trigger)

# === Email Setup ===
SENDER_EMAIL = "electricitycommissionofindia@gmail.com"
SENDER_PASSWORD = "tszyszoklxwssjma"  # App password (NOT your Gmail password)
RECEIVER_EMAIL = "niranjan13012007@gmail.com"

# === AI Recommendation Logic ===
def get_power_advice(power):
    if power > 10:
        return {
            "status": "CRITICAL",
            "message": "⚠ Very high usage! Turn off heavy appliances like AC, oven, or washing machine."
        }
    elif power > 5:
        return {
            "status": "HIGH",
            "message": "🔍 High usage detected. Consider reducing usage—check water heater, fridge, or motor."
        }
    elif power > 2:
        return {
            "status": "MEDIUM",
            "message": "✅ Moderate usage. Consider turning off unused lights or fans."
        }
    else:
        return {
            "status": "LOW",
            "message": "🟢 Low power usage. All systems running efficiently."
        }

# === Send Email Alert ===
def send_email(subject, body):
    try:
        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['To'] = RECEIVER_EMAIL
        msg['Subject'] = subject

        # Add the link to the email body
        body += "\n\n Click this link to turn off the device \n" \
                "https://blynk.cloud/dashboard/483562/global/devices/1/organization/483562/devices/1570864/dashboard"
        
        msg.attach(MIMEText(body, 'plain'))

        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, msg.as_string())
            print("✅ Email sent successfully.")
    except Exception as e:
        print("❌ Failed to send email:", e)

# === Read Power from Blynk ===
def get_power_from_blynk():
    try:
        url = f"https://blynk.cloud/external/api/get?token={BLYNK_TOKEN}&{VIRTUAL_PIN_POWER}"
        response = requests.get(url)
        if response.status_code == 200:
            return float(response.text)
        else:
            print("❌ Failed to fetch power. Code:", response.status_code)
            return None
    except Exception as e:
        print("❌ Blynk power fetch error:", e)
        return None

# === Turn Off Device ===
def turn_off_device():
    try:
        url = f"https://blynk.cloud/external/api/update?token={BLYNK_TOKEN}&{VIRTUAL_PIN_CONTROL}=0"
        response = requests.get(url)
        if response.status_code == 200:
            print("🔌 Device turned OFF via Blynk.")
        else:
            print("❌ Failed to turn off device. Code:", response.status_code)
    except Exception as e:
        print("❌ Error turning off device:", e)

# === Check for User Text Input ===
def check_user_text_input():
    try:
        url = f"https://blynk.cloud/external/api/get?token={BLYNK_TOKEN}&{VIRTUAL_PIN_TEXT_INPUT}"
        response = requests.get(url)
        if response.status_code == 200:
            user_input = response.text.strip().lower()
            print(f"📝 User typed: {user_input}")
            return user_input == "off"
        return False
    except Exception as e:
        print("❌ Error reading user input:", e)
        return False

# === Main Loop ===
print("🚀 AI Energy Bot is running...")

while True:
    power = get_power_from_blynk()
    if power is not None:
        print(f"\n⚡ Power Usage: {power} W")
        advice = get_power_advice(power)
        print(f"🤖 Status: {advice['status']}")
        print(f"🧠 Advice: {advice['message']}")

        # Send alert for high or critical power
        if advice['status'] in ["HIGH", "CRITICAL"]:
            send_email(
                subject=f"ALERT: {advice['status']} Power Usage Detected",
                body=f"⚡ Power: {power} W\n\n{advice['message']}"
            )

        # Check if user typed 'off'
        if check_user_text_input():
            turn_off_device()

    time.sleep(5)
