import requests
import mysql.connector
import time

# Blynk credentials
BLYNK_TOKEN = "sGa2Ws1F_FjLjdZYWB-zk4Wf2kjCozkG"
VIRTUAL_PIN = "V3"

# MySQL connection
conn = mysql.connector.connect(
    host="localhost",
    user="root",
    password="Niranjan@123",
    database="energy_db"
)
cursor = conn.cursor()
cursor.execute("CREATE TABLE IF NOT EXISTS energy_data (id INT AUTO_INCREMENT PRIMARY KEY, energy FLOAT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)")

while True:
    try:
        url = f"https://blynk.cloud/external/api/get?token={BLYNK_TOKEN}&{VIRTUAL_PIN}"
        response = requests.get(url)
        energy = float(response.text)
        cursor.execute("INSERT INTO energy_data (energy) VALUES (%s)", (energy,))
        conn.commit()
        print(f"Inserted: {energy}")
    except Exception as e:
        print("Error:", e)
    time.sleep(60)
