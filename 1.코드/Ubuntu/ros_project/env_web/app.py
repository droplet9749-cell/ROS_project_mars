from flask import Flask, render_template, jsonify, request
import pymysql
from pymysql.cursors import DictCursor
from datetime import datetime

app = Flask(__name__)

# ✅ 여기 DB 정보만 너 환경에 맞게 수정
DB_CONFIG = {
    "host": "localhost",      # DB가 같은 머신이면 보통 localhost/127.0.0.1
    "user": "turtle",
    "password": "1234",
    "database": "turtle_env",
    "cursorclass": DictCursor,
    "autocommit": True,
}

def get_conn():
    return pymysql.connect(**DB_CONFIG)

@app.route("/")
def dashboard():
	    # 최근 50개 표로 뿌리기
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute("""
            SELECT
                id,
                temperature,
                humidity,
                cds1, cds2, cds3,
                distance,
                ir,
                gas,
                created_at
            FROM env_data
            ORDER BY created_at DESC
            LIMIT 50
        """)
        rows = cur.fetchall()
    conn.close()
    return render_template("dashboard.html", rows=rows)

# 그래프용: 최근 N개를 시간 오름차순으로 반환 (기본 200개)
@app.route("/api/env")
def api_env():
    limit = int(request.args.get("limit", 300))
    limit = max(10, min(limit, 2000))  # 안전장치

	# 최근 10분 업데이트 / 이하 if 문 추가
    minutes = request.args.get("minutes")  # 예: 10

    conn = get_conn()
    with conn.cursor() as cur:
        if minutes is not None:
            minutes = int(minutes)
            minutes = max(1, min(minutes, 1440))  # 1분~24시간
            cur.execute(f"""
                SELECT
                    temperature,
                    humidity,
                    cds1, cds2, cds3,
                    distance,
                    ir,
                    gas,
                    created_at
                FROM env_data
                ORDER BY created_at DESC
                LIMIT {limit}
            """)
            rows = cur.fetchall()
        else:
            cur.execute(f"""
                SELECT
                    temperature, humidity,
                    cds1, cds2, cds3,
                    distance, ir, gas,
                    created_at
                FROM env_data
                ORDER BY created_at DESC
                LIMIT {limit}
            """)
            rows = cur.fetchall()
            rows.reverse()

    conn.close()

    # DESC로 뽑았으니 그래프는 시간순으로 뒤집기
    rows.reverse()

    # Chart.js에서 쓰기 좋은 형태로 변환
    data = {
        "time": [r["created_at"].strftime("%Y-%m-%d %H:%M:%S") for r in rows],
        "temperature": [r["temperature"] for r in rows],
        "humidity": [r["humidity"] for r in rows],
        "cds1": [r["cds1"] for r in rows],
        "cds2": [r["cds2"] for r in rows],
        "cds3": [r["cds3"] for r in rows],
        "distance": [r["distance"] for r in rows],
        "ir": [r["ir"] for r in rows],
        "gas": [r["gas"] for r in rows],
    }
    return jsonify(data)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5051, debug=True)
