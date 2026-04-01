import serial
import json
import requests

# OpenCR serial
ser = serial.Serial('/dev/ttyACM0',115200,timeout=1)

SERVER_URL = "http://10.10.141.58:5000/sensor"

print("Raspberry receiver started")

while True:
    try:
        line = ser.readline().decode(errors='ignore').strip()

        if not line:
            continue

        if not (line.startswith("{") and line.endswith("}")):
            continue

        data = json.loads(line)

        print("FROM OpenCR RAW:", line)
        print("KEYS:", list(data.keys()))

        print("FROM OpenCR:", data)

        r = requests.post(SERVER_URL, json=data)

        print("SERVER RESPONSE:", r.status_code)

    except Exception as e:
        print("Error:", e)
