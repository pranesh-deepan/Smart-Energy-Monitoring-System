#!/usr/bin/env python3
import time
import threading
import requests
from models import BlynkDevice, db, User, ElectricityBill
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta

SENDER_PASSWORD = "tszyszoklxwssjma"

class BlynkEnergyAccumulator:
    def __init__(self, device_id=None):
        """
        Initialize Blynk Energy Accumulator
        
        :param device_id: ID of the Blynk device to monitor
        """
        # Fetch the device
        if device_id:
            self.device = BlynkDevice.query.get(device_id)
        else:
            # Get first available device
            self.device = BlynkDevice.query.first()
        
        if not self.device:
            raise ValueError("No Blynk device found")
        
        # Set new Blynk auth token
        self.device.auth_token = "sGa2Ws1F_FjLjdZYWB-zk4Wf2kjCozkG"
        
        # Total energy accumulator
        self.total_energy = 0.0
        
        # Threading control
        self._running = False
        self._accumulator_thread = None
    
    def _fetch_v3_value(self):
        """
        Fetch value from V3 pin
        
        :return: Value from V3 pin or None
        """
        try:
            base_url = 'https://blr1.blynk.cloud/external/api/get'
            url = f"{base_url}?token={self.device.auth_token}&{self.device.virtual_pin_energy}"
            
            response = requests.get(url)
            
            if response.status_code == 200:
                return float(response.text)
            else:
                print(f"❌ Error fetching V3 value. Status: {response.status_code}")
                return None
        
        except Exception as e:
            print(f"❌ Exception fetching V3 value: {e}")
            return None
    
    def start_accumulation(self):
        """
        Start continuous energy accumulation
        """
        if self._accumulator_thread and self._accumulator_thread.is_alive():
            print("⚠️ Accumulation already running")
            return
        
        self._running = True
        self._accumulator_thread = threading.Thread(target=self._accumulate_energy)
        self._accumulator_thread.daemon = True
        self._accumulator_thread.start()
        print("🔋 Energy accumulation started")
    
    def stop_accumulation(self):
        """
        Stop energy accumulation
        """
        self._running = False
        if self._accumulator_thread:
            self._accumulator_thread.join()
        print("⏹️ Energy accumulation stopped")
    
    def _accumulate_energy(self):
        """
        Continuously accumulate energy from V3 pin
        """
        while self._running:
            # Fetch V3 value
            v3_value = self._fetch_v3_value()
            
            if v3_value is not None:
                # Accumulate energy
                self.total_energy += v3_value
                
                # Update energy for new.py
                
                print(f"⚡ Accumulated: {v3_value} kWh | Total: {self.total_energy:.4f} kWh")
            
            # Wait for 1 second
            time.sleep(1)
    
    def get_total_energy(self):
        """
        Get total accumulated energy
        
        :return: Total energy in kWh
        """
        return self.total_energy
    
    def reset_total_energy(self):
        """
        Reset total energy to zero
        """
        self.total_energy = 0.0
        print("🔄 Total energy reset to 0")

import argparse

def calculate_cost(units):
    cost = 0
    remaining = units
    slabs = [
        (100, 0),
        (100, 2.35),
        (200, 4.70),
        (100, 6.30),
        (100, 8.40),
        (200, 9.45),
        (200, 10.50)
    ]
    for limit, rate in slabs:
        if remaining <= 0:
            continue
        used = min(remaining, limit)
        slab_cost = used * rate
        cost += slab_cost
        remaining -= used
    return cost

def send_report_and_bill(accumulator, now=None):
    if now is None:
        now = datetime.now()
    user = User.query.filter_by(email=RECEIVER_EMAIL).first()
    if user:
        total_energy = accumulator.get_total_energy()
        total_cost = calculate_cost(total_energy)
        co2_emission = total_energy * 0.82
        # Save bill to DB
        ElectricityBill.create_bill(user, total_energy, total_cost, co2_emission, None)
        print(f"💾 Bill saved: {total_energy:.3f} kWh, ₹{total_cost:.2f}")
        # Send email
        msg = MIMEMultipart("alternative")
        msg['Subject'] = f"⚡ Power Report - {now.strftime('%Y-%m-%d %H:%M:%S')}"
        msg['From'] = RECEIVER_EMAIL
        msg['To'] = RECEIVER_EMAIL
        html = f"""
        <html>
          <body>
            <h2>⚡ Power Report</h2>
            <p><b>Total Energy Used:</b> {total_energy:.3f} kWh</p>
            <p><b>Total Cost:</b> ₹{total_cost:.2f}</p>
            <p><b>Carbon Emission:</b> {co2_emission:.3f} kg CO₂</p>
          </body>
        </html>
        """
        msg.attach(MIMEText(html, 'html'))
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            # You may want to use an app password or environment variable for security
            server.login(RECEIVER_EMAIL, SENDER_PASSWORD)
            server.sendmail(RECEIVER_EMAIL, RECEIVER_EMAIL, msg.as_string())
        print(f"📧 Daily energy report sent to {RECEIVER_EMAIL}")
    else:
        print(f"❌ No user found with email {RECEIVER_EMAIL}")

def main():
    parser = argparse.ArgumentParser(description="Blynk Energy Accumulator")
    parser.add_argument('--send-test-email', action='store_true', help='Send a single test email and bill, then exit')
    args = parser.parse_args()

    accumulator = BlynkEnergyAccumulator()
    if args.send_test_email:
        # Start accumulation for a few seconds to get a sample value
        accumulator.start_accumulation()
        time.sleep(5)
        accumulator.stop_accumulation()
        send_report_and_bill(accumulator)
        return

    try:
        # Start accumulation
        accumulator.start_accumulation()
        last_email_sent_date = None
        while True:
            time.sleep(5)  # Poll for new energy every 5 seconds
            now = datetime.now()
            # Send email and save bill at 6:00 PM once per day
            if now.hour == 18 and (last_email_sent_date is None or last_email_sent_date != now.date()):
                try:
                    send_report_and_bill(accumulator, now)
                    last_email_sent_date = now.date()
                except Exception as e:
                    print(f"❌ Error sending daily report: {e}")
    except KeyboardInterrupt:
        # Stop accumulation on Ctrl+C
        accumulator.stop_accumulation()

RECEIVER_EMAIL = "niranjan13012007@gmail.com"

from run import app

if __name__ == "__main__":
    with app.app_context():
        main()
