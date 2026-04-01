from flask import Flask, request, jsonify
import pymysql

app = Flask(__name__)

# =========================
# DB 연결
# =========================
def get_db():
    return pymysql.connect(
        host="localhost",
        user="turtle",
        password="1234",
        database="turtle_env",
        cursorclass=pymysql.cursors.DictCursor
    )

# =========================
# DB 저장 함수
# =========================
def save_to_db(data):
    conn = get_db()
    cur = conn.cursor()

    # ir, gas 컬럼 추가 및 쿼리 수정
    sql = """
    INSERT INTO env_data
    (cds1, cds2, cds3, temperature, humidity, distance, ir, gas)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """

    # 에러 방지를 위해 get() 메서드 사용 (데이터가 없으면 0으로 처리)
    cur.execute(sql, (
        data.get("cds1", 0),
        data.get("cds2", 0),
        data.get("cds3", 0),
        data.get("temp", 0),
        data.get("hum", 0),
        data.get("distance", 0),
        data.get("ir", 0),   # 추가된 IR 센서 데이터
        data.get("gas", 0)   # 추가된 GAS 센서 데이터
    ))

    conn.commit()
    cur.close()
    conn.close()

# =========================
# 센서 데이터 수신 API (라즈베리 → 서버)
# =========================
@app.route("/sensor", methods=["POST"])
def receive_sensor():
    data = request.get_json()
    print("RECEIVED:", data)

    try:
        save_to_db(data)
        return jsonify({"status": "saved"}), 200
    except Exception as e:
        print(f"DB Insert Error: {e}")
        return jsonify({"error": str(e)}), 500

# =========================
# 최신 센서 조회 API
# =========================
@app.route("/api/latest", methods=["GET"])
def get_latest():
    conn = get_db()
    cur = conn.cursor()

    sql = """
    SELECT *
    FROM env_data
    ORDER BY id DESC
    LIMIT 1
    """

    cur.execute(sql)
    result = cur.fetchone()

    cur.close()
    conn.close()

    if result:
        return jsonify(result)
    else:
        return jsonify({"error": "no data"}), 404

# =========================
# 서버 실행
# =========================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050, debug=True)
