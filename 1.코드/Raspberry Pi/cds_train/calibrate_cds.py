#!/usr/bin/env python3
import serial
import json
import time
import os

def main():
    port = '/dev/ttyUSB1'  # 1번 포트 사용
    baudrate = 57600

    # 1. 동적 경로 설정 (어디서 실행하든 config 폴더를 정확히 찾음)
    # 현재 실행 중인 파일(calibrate_cds.py)의 절대 경로를 기준으로 부모 폴더(hwi_turtle)를 찾습니다.
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    config_dir = os.path.join(project_root, 'config')
    calib_file = os.path.join(config_dir, 'cds_calib.json')

    # config 폴더가 존재하지 않으면 자동으로 생성합니다.
    if not os.path.exists(config_dir):
        os.makedirs(config_dir)

    print("=" * 50)
    print(" 🌞 조도 센서(CDS) 캘리브레이션 모드 시작 🌞")
    print("=" * 50)

    try:
        ser = serial.Serial(port, baudrate, timeout=0.1)
    except Exception as e:
        print(f"❌ 시리얼 연결 실패. OpenCR 연결 상태를 확인하세요: {e}")
        return

    cds_min = {'L': 4095, 'C': 4095, 'R': 4095}
    cds_max = {'L': 0, 'C': 0, 'R': 0}

    # 15초 동안 캘리브레이션 진행
    CALIB_DURATION = 30.0
    start_time = time.time()

    print(f"\n[안내] {CALIB_DURATION}초 동안 센서를 손으로 가렸다가, 밝은 빛을 비춰주세요!")
    print("데이터 수집 중...\n")

    while True:
        elapsed = time.time() - start_time
        if elapsed > CALIB_DURATION:
            break

        if ser.in_waiting > 0:
            try:
                raw_data = ser.readline().decode('utf-8', errors='ignore').strip()
                if not raw_data or '{' not in raw_data: continue

                clean_line = raw_data.replace(',}', '}')
                parsed = json.loads(clean_line)

                if all(k in parsed for k in ('cds1', 'cds2', 'cds3')):
                    r_L, r_C, r_R = int(parsed['cds1']), int(parsed['cds2']), int(parsed['cds3'])

                    # 최소/최대값 갱신
                    cds_min['L'] = min(cds_min['L'], r_L); cds_max['L'] = max(cds_max['L'], r_L)
                    cds_min['C'] = min(cds_min['C'], r_C); cds_max['C'] = max(cds_max['C'], r_C)
                    cds_min['R'] = min(cds_min['R'], r_R); cds_max['R'] = max(cds_max['R'], r_R)

                    # 진행 상황 출력 (한 줄로 덮어쓰기)
                    print(f"\r남은 시간: {CALIB_DURATION - elapsed:.1f}초 | 현재 MAX -> L:{cds_max['L']} C:{cds_max['C']} R:{cds_max['R']}", end="")
            except Exception:
                pass

    ser.close()

    # 2. 캘리브레이션 결과 저장
    calib_data = {'min': cds_min, 'max': cds_max}
    with open(calib_file, 'w') as f:
        json.dump(calib_data, f, indent=4)

    print("\n\n✅ 캘리브레이션 완료! 데이터가 성공적으로 저장되었습니다.")
    print(f"저장된 파일: {calib_file}")
    print(f"MIN 값: {cds_min}")
    print(f"MAX 값: {cds_max}")
    print("이제 mars_core.py를 실행하여 탐사를 시작할 수 있습니다!\n")

if __name__ == '__main__':
    main()
