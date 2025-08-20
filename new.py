#!/usr/bin/env python3
import os
import sys
import time
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import User, BlynkDevice
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib

# Database connection
engine = create_engine('sqlite:///user_management.db')
Session = sessionmaker(bind=engine)

# Email configuration
SENDER_EMAIL = os.getenv('SENDER_EMAIL', 'electricitycommissionofindia@gmail.com')
SENDER_PASSWORD = os.getenv('SENDER_PASSWORD', 'tszyszoklxwssjma')

# Tiered electricity pricing
def calculate_cost(units):
    cost = 0
    breakdown = []
    
    # Electricity slab rates (example rates, adjust as needed)
    slabs = [
        (100, 0),     # First 100 units free
        (100, 2.35),  # Next 100 units
        (200, 4.70),  # Next 200 units
        (100, 6.30),  # Next 100 units
        (100, 8.40),  # Next 100 units
        (200, 9.45),  # Next 200 units
        (float('inf'), 10.50)  # Remaining units
    ]
    
    remaining = units
    for limit, rate in slabs:
        if remaining <= 0:
            break
        
        used = min(remaining, limit)
        slab_cost = used * rate
        cost += slab_cost
        breakdown.append((used, rate, slab_cost))
        remaining -= used
    
    return cost, breakdown

def send_daily_report(current_user, total_energy):
    try:
        # Calculate cost and breakdown
        total_cost, cost_breakdown = calculate_cost(total_energy)
        co2_emission = total_energy * 0.82  # CO2 calculation

        # Prepare email for current user
        msg = MIMEMultipart("alternative")
        msg['Subject'] = f"📊 Daily Energy Report - {datetime.now().strftime('%Y-%m-%d')}"
        msg['From'] = SENDER_EMAIL
        msg['To'] = current_user.email

        # HTML email content
        html = f"""
        <html>
          <body>
            <h2>📈 Daily Energy Consumption</h2>
            <p><b>Total Energy Used:</b> {total_energy:.3f} kWh</p>
            <p><b>Total Cost:</b> ₹{total_cost:.2f}</p>
            <p><b>Carbon Emission:</b> {co2_emission:.3f} kg CO₂</p>
            
            <h3>Cost Breakdown</h3>
            <table border="1" cellpadding="5">
              <tr><th>Units</th><th>Rate</th><th>Cost</th></tr>
              {''.join(f'<tr><td>{used}</td><td>₹{rate}</td><td>₹{cost:.2f}</td></tr>' for used, rate, cost in cost_breakdown)}
            </table>
          </body>
        </html>
        """

        msg.attach(MIMEText(html, 'html'))

        # Send email
        try:
            with smtplib.SMTP('smtp.gmail.com', 587) as server:
                server.starttls()
                server.login(SENDER_EMAIL, SENDER_PASSWORD)
                server.sendmail(SENDER_EMAIL, current_user.email, msg.as_string())
                print(f"✅ Email sent to {current_user.email}")
        except Exception as e:
            print(f"❌ Email error for {current_user.email}: {e}")

    except Exception as e:
        print(f"❌ Error in daily report: {e}")

def main(current_user=None, total_energy=0.0):
    """Main function to send daily energy report
    
    :param current_user: User to send report to
    :param total_energy: Total energy accumulated from Blynk V3
    """
    # If no current user is provided, exit
    if current_user is None:
        print("❌ No user session found. Cannot send daily report.")
        return
    
    while True:
        now = datetime.now()
        
        # Check if it's 6 PM
        if now.hour == 18 and now.minute == 0:
            # Send daily report
            send_daily_report(current_user, total_energy)
            
            # Sleep to prevent multiple sends
            time.sleep(60)
        
        time.sleep(30)  # Check every 30 seconds

if __name__ == "__main__":
    print("This script should be imported and run with a current user and total energy.")