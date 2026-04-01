import serial
import json
import pymysql

ser = serial.Serial('/dev/ttyACM0', 9600, timeout=1)

conn = pymysql.connect(
    host='localhost',
    user='root',
    password='비밀번호',
    database='sensor_db'
)
cur = conn.cursor()

while True:
    try:
        line = ser.readline().decode(errors='ignore').strip()
        print("RAW:", line)

        if not line.startswith("{") or not line.endswith("}"):
            continue

        data = json.loads(line)
        print("PARSED:", data)

        cds1 = data.get("cds1", 0)
        cds2 = data.get("cds2", 0)
        cds3 = data.get("cds3", 0)
        temp = data.get("temp", 0)
        hum = data.get("hum", 0)
        distance = data.get("distance", None)

        sql = """
        INSERT INTO env_data
        (cds1, cds2, cds3, temperature, humidity, distance)
        VALUES (%s, %s, %s, %s, %s, %s)
        """
        cur.execute(sql, (cds1, cds2, cds3, temp, hum, distance))
        conn.commit()

    except json.JSONDecodeError:
        print("JSON 깨짐 → skip")

    except Exception as e:
        print("Error:", e)
