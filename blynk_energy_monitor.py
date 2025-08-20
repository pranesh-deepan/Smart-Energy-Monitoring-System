import os
import sys
import requests
import time
import threading
import django

# Add the project directory to Python path
project_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(project_dir)

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()

from models import BlynkDevice, db
from sqlalchemy.orm import sessionmaker

class BlynkEnergyMonitor:
    def __init__(self, device_id=None):
        """
        Initialize Blynk Energy Monitor
        
        :param device_id: ID of the Blynk device to monitor
        """
        # Create a database session
        Session = sessionmaker(bind=db.engine)
        self.session = Session()

        # Fetch device details if device_id is provided
        if device_id:
            self.device = self.session.query(BlynkDevice).get(device_id)
            if not self.device:
                raise ValueError(f"No device found with ID {device_id}")
        else:
            # If no specific device, get the first available device
            self.device = self.session.query(BlynkDevice).first()
            if not self.device:
                raise ValueError("No Blynk devices found in the database")

        # Device-specific configuration
        self.auth_token = self.device.auth_token
        self.virtual_pin = self.device.virtual_pin_energy  # Use device's energy pin
        self.base_url = 'https://blr1.blynk.cloud/external/api/get'
        
        # Accumulated energy variable
        self.total_energy = 0.0
        
        # Thread control
        self._running = False
        self._monitor_thread = None
        
        print(f"Monitoring device: {self.device.device_name}")
    
    def _fetch_pin_value(self):
        """
        Fetch value from specified Blynk virtual pin
        
        :return: Float value or None if fetch fails
        """
        try:
            response = requests.get(
                f'{self.base_url}?token={self.auth_token}&{self.virtual_pin}'
            )
            
            if response.status_code == 200:
                return float(response.text)
            else:
                print(f"Error fetching data: HTTP {response.status_code}")
                return None
        
        except Exception as e:
            print(f"Error in data fetch: {e}")
            return None
    
    def start_monitoring(self):
        """
        Start continuous monitoring of the virtual pin
        Accumulates energy values every second
        """
        self._running = True
        self._monitor_thread = threading.Thread(target=self._monitoring_loop)
        self._monitor_thread.daemon = True
        self._monitor_thread.start()
        print(f"Started monitoring Blynk pin {self.virtual_pin}")
    
    def _monitoring_loop(self):
        """
        Continuous monitoring loop
        Runs in a separate thread
        """
        while self._running:
            value = self._fetch_pin_value()
            
            if value is not None:
                self.total_energy += value
                print(f"Current Energy Reading: {value} | Total Accumulated: {self.total_energy}")
            
            time.sleep(1)  # Wait for 1 second between readings
    
    def stop_monitoring(self):
        """
        Stop the monitoring thread
        """
        self._running = False
        if self._monitor_thread:
            self._monitor_thread.join()
        print("Monitoring stopped")
    
    def reset_total_energy(self):
        """
        Reset the total energy accumulation
        """
        self.total_energy = 0.0
        print("Total energy reset to 0")

# Example usage
if __name__ == '__main__':
    # Fetch all Blynk devices and monitor
    Session = sessionmaker(bind=db.engine)
    session = Session()
    
    try:
        # Get all Blynk devices
        devices = session.query(BlynkDevice).all()
        
        if not devices:
            print("No Blynk devices found in the database.")
            sys.exit(1)
        
        # Monitor devices
        monitors = []
        for device in devices:
            try:
                monitor = BlynkEnergyMonitor(device.id)
                monitor.start_monitoring()
                monitors.append(monitor)
            except Exception as e:
                print(f"Error monitoring device {device.device_name}: {e}")
        
        # Keep main thread running
        while True:
            time.sleep(10)
            print("\nCurrent Energy Accumulations:")
            for monitor in monitors:
                print(f"{monitor.device.device_name}: {monitor.total_energy} kWh")
    
    except KeyboardInterrupt:
        # Stop all monitors on Ctrl+C
        for monitor in monitors:
            monitor.stop_monitoring()
    
    finally:
        # Close database session
        session.close()
