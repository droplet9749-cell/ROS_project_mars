#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from rclpy.duration import Duration
from rclpy.qos import qos_profile_sensor_data

from sensor_msgs.msg import BatteryState, Imu, LaserScan, Range
from geometry_msgs.msg import Twist, TransformStamped
from std_msgs.msg import String

from tf2_ros import Buffer, TransformListener
from tf2_ros.static_transform_broadcaster import StaticTransformBroadcaster

import math
import time
import os
import subprocess
import serial
import json
import Adafruit_DHT
import requests
import threading 

# ==========================================================
# 1. 에너지 최적화 엔진 (MarsEnergyOptimizer)
# ==========================================================
class MarsEnergyOptimizer:
    def __init__(self):
        self.FACTOR_MARS_ENV = 0.6             
        self.FACTOR_DIST_COST = 0.7              
        self.MAX_SEARCH_RANGE_CM = 1000.0  
        self.AVG_GROUND_TEMP = -20.0       
        self.TEMP_CORRECTION = 0.2         
        self.TIME_DECAY_FACTOR = 0.82      

    def calculate_spot_score(self, lux_0_to_1000, temp, distance_meters, data_age_sec):
        simulated_lux = lux_0_to_1000 * self.FACTOR_MARS_ENV
        temp_efficiency = 1.0 if temp >= self.AVG_GROUND_TEMP else (1.0 - self.TEMP_CORRECTION)
        environmental_score = simulated_lux * temp_efficiency

        distance_cm = distance_meters * 100.0
        dist_ratio = distance_cm / self.MAX_SEARCH_RANGE_CM
        if dist_ratio > 1.0: dist_ratio = 1.0
        distance_penalty = (dist_ratio * 1000.0) * self.FACTOR_DIST_COST

        net_profit = environmental_score - distance_penalty
        hours_passed = data_age_sec / 3600.0
        time_reliability = self.TIME_DECAY_FACTOR ** hours_passed 
        score = net_profit * time_reliability
        return score, environmental_score

    def find_best_spot(self, current_pose, spot_database):
        best_spot = None
        highest_score = -float('inf')
        current_time = time.time()

        for spot in spot_database:
            dist_m = math.sqrt((current_pose[0] - spot['x'])**2 + (current_pose[1] - spot['y'])**2)
            age_sec = current_time - spot['time']
            score, env_score = self.calculate_spot_score(spot['lux'], spot['temp'], dist_m, age_sec)

            if score > highest_score:
                highest_score = score
                best_spot = spot
                best_spot['final_score'] = score 
        return best_spot

# ==========================================================
# 2. 메인 통합 제어기 (MarsRoverController)
# ==========================================================
class MarsRoverController(Node):
    def __init__(self):
        super().__init__('mars_rover_core_node')
        
        # ---- 상태 및 하드웨어 데이터 변수 ----
        self.state = "EXPLORING"       
        self.is_low_battery_mode = False
        self.battery_percent = 100.0
        self.current_pitch = 0.0
        self.lidar_running = True 
        
        self.current_lux = 0.0   
        self.current_temp = 20.0 
        
        self.latest_cds = {'L': 0, 'C': 0, 'R': 0}
        self.latest_ir = 1
        self.latest_gas = 0
        self.latest_hum = 0.0       
        self.latest_distance = 0.0  

        self.SERVER_URL = "http://10.10.141.58:5051/sensor" # IP/Port 확인 필수
        self.memory_spots = [] 
        self.optimizer = MarsEnergyOptimizer()

        # ---- 센서 프레임(TF) 변수 설정 ----
        self.us_frame_id = 'ultrasonic_front_link'
        self.ir_frame_id = 'ir_cliff_link'

        # ---- 퍼블리셔 설정 ----
        self.pub_ultrasonic = self.create_publisher(LaserScan, '/ultrasonic/scan', qos_profile_sensor_data)
        self.pub_cliff = self.create_publisher(Range, '/ir_cliff_range', 10)
        self.pub_sensor_json = self.create_publisher(String, '/sensor_data', 10)
        self.pub_cmd_vel = self.create_publisher(Twist, '/cmd_vel', 10)
        self.pub_status = self.create_publisher(String, '/robot_status', 10)

        # TF 브로드캐스터
        self.tf_broadcaster = StaticTransformBroadcaster(self)
        self.publish_static_tf()

        # ---- OpenCR 직렬 통신 ----
        self.port = '/dev/ttyUSB1' # 1번 포트 사용 이력 반영
        self.baudrate = 57600
        try:
            self.ser = serial.Serial(self.port, self.baudrate, timeout=0.1)
            self.get_logger().info("✅ OpenCR 시리얼 연결 성공!")
        except serial.SerialException as e:
            self.get_logger().error(f"❌ 시리얼 연결 실패: {e}")
            raise e

        # 캘리브레이션 변수
        self.start_time = time.time()
        self.is_calibrated = False
        self.cds_min = {'L': 4095, 'C': 4095, 'R': 4095}
        self.cds_max = {'L': 0, 'C': 0, 'R': 0}

        # ---- RPi DHT 하드웨어 ----
        self.dht_sensor = Adafruit_DHT.DHT11
        self.dht_pin = 4

        # ---- ROS 구독자 설정 ----
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)
        self.sub_battery = self.create_subscription(BatteryState, '/battery_state', self.battery_cb, 10)
        self.sub_imu = self.create_subscription(Imu, '/imu', self.imu_cb, 10)

        # ---- 타이머 설정 ----
        self.timer_serial = self.create_timer(0.05, self.serial_timer_callback) # 20Hz
        self.timer_dht = self.create_timer(2.0, self.dht_timer_callback)        # 0.5Hz
        self.timer_main = self.create_timer(1.0, self.control_loop)             # 1Hz
        self.last_record_time = time.time()
        
        self.get_logger().info("🚀 Mars Rover Core (Sensor + Nav + DB) Started!")

    def publish_static_tf(self):
        # 1. 초음파 센서 (1층 바닥 앞쪽 끝)
        t_us = TransformStamped()
        t_us.header.stamp = self.get_clock().now().to_msg()
        t_us.header.frame_id = 'base_link'
        t_us.child_frame_id = self.us_frame_id
        t_us.transform.translation.x = 0.07
        t_us.transform.translation.y = 0.00
        t_us.transform.translation.z = 0.01
        t_us.transform.rotation.w = 1.0

        # 2. 적외선 센서 (2층 바닥, 1cm 돌출)
        t_ir = TransformStamped()
        t_ir.header.stamp = self.get_clock().now().to_msg()
        t_ir.header.frame_id = 'base_link'
        t_ir.child_frame_id = self.ir_frame_id
        t_ir.transform.translation.x = 0.08
        t_ir.transform.translation.y = 0.00
        t_ir.transform.translation.z = 0.05
        t_ir.transform.rotation.w = 1.0

        self.tf_broadcaster.sendTransform([t_us, t_ir])

    def serial_timer_callback(self):
        if self.ser.in_waiting > 0:
            try:
                raw_data = self.ser.readline().decode('utf-8', errors='ignore').strip()
                if not raw_data or '{' not in raw_data: return
                
                clean_line = raw_data.replace(',}', '}')
                parsed_data = json.loads(clean_line)

                # 1. 낭떠러지 및 가스 데이터 업데이트
                if 'ir' in parsed_data: 
                    self.latest_ir = int(parsed_data['ir'])
                    self.publish_cliff_range(self.latest_ir)
                if 'gas' in parsed_data: 
                    self.latest_gas = int(parsed_data['gas'])

                # 2. 초음파 데이터 업데이트 및 가상 스캔 발행
                if 'distance' in parsed_data:
                    self.latest_distance = float(parsed_data['distance'])
                    self.publish_ultrasonic_scan(self.latest_distance / 100.0)

                # 3. 조도 센서 캘리브레이션 및 정규화
                if all(k in parsed_data for k in ('cds1', 'cds2', 'cds3')):
                    r_L, r_C, r_R = int(parsed_data['cds1']), int(parsed_data['cds2']), int(parsed_data['cds3'])
                    elapsed_time = time.time() - self.start_time

                    if elapsed_time < 30.0:
                        self.cds_min['L'] = min(self.cds_min['L'], r_L); self.cds_max['L'] = max(self.cds_max['L'], r_L)
                        self.cds_min['C'] = min(self.cds_min['C'], r_C); self.cds_max['C'] = max(self.cds_max['C'], r_C)
                        self.cds_min['R'] = min(self.cds_min['R'], r_R); self.cds_max['R'] = max(self.cds_max['R'], r_R)
                        self.latest_cds = {'L': 0, 'C': 0, 'R': 0}
                        self.current_lux = 0.0
                        return 
                    else:
                        if not self.is_calibrated:
                            self.get_logger().info(f"✅ 30초 캘리브레이션 완료! 학습범위 C:{self.cds_min['C']}~{self.cds_max['C']}")
                            self.is_calibrated = True

                    def normalize(val, min_v, max_v):
                        if max_v - min_v == 0: return 0 
                        return max(0, min(1000, int((val - min_v) * 1000 / (max_v - min_v))))

                    self.latest_cds['L'] = normalize(r_L, self.cds_min['L'], self.cds_max['L'])
                    self.latest_cds['C'] = normalize(r_C, self.cds_min['C'], self.cds_max['C'])
                    self.latest_cds['R'] = normalize(r_R, self.cds_min['R'], self.cds_max['R'])
                    self.current_lux = sum(self.latest_cds.values()) / 3.0
            except Exception: pass

    def publish_ultrasonic_scan(self, dist_m):
        us_scan = LaserScan()
        us_scan.header.stamp = self.get_clock().now().to_msg()
        us_scan.header.frame_id = self.us_frame_id
        us_scan.angle_min, us_scan.angle_max = -0.13, 0.13
        us_scan.range_min, us_scan.range_max = 0.02, 2.0
        us_scan.angle_increment = (us_scan.angle_max - us_scan.angle_min) / 6.0
        
        r = dist_m if 0.02 < dist_m < 2.0 else float('inf')
        us_scan.ranges = [r] * 7
        self.pub_ultrasonic.publish(us_scan)

    def publish_cliff_range(self, ir_val):
        msg = Range()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = self.ir_frame_id
        msg.radiation_type = Range.INFRARED
        msg.range = 0.02 if ir_val == 1 else 0.5 
        msg.min_range, msg.max_range = 0.0, 0.5
        self.pub_cliff.publish(msg)

    def dht_timer_callback(self):
        humidity, temperature = Adafruit_DHT.read(self.dht_sensor, self.dht_pin)
        if temperature is not None: self.current_temp = temperature 
        if humidity is not None: self.latest_hum = humidity

    def battery_cb(self, msg):
        self.battery_percent = msg.percentage
        self.check_battery_status()

    def imu_cb(self, msg):
        q = msg.orientation
        sinp = 2.0 * (q.w * q.y - q.z * q.x)
        pitch_rad = math.copysign(math.pi / 2, sinp) if abs(sinp) >= 1 else math.asin(sinp)
        self.current_pitch = math.degrees(pitch_rad)

    def get_current_pose(self):
        try:
            t = self.tf_buffer.lookup_transform('map', 'base_link', rclpy.time.Time())
            return t.transform.translation.x, t.transform.translation.y
        except Exception: return None

    def send_data_to_server(self):
        payload = {
            "cds1": self.latest_cds['L'], "cds2": self.latest_cds['C'], "cds3": self.latest_cds['R'],
            "distance": self.latest_distance, "ir": self.latest_ir, "gas": self.latest_gas,
            "temp": self.current_temp, "hum": self.latest_hum, "battery": round(self.battery_percent, 1)
        }
        
        json_str = String()
        json_str.data = json.dumps(payload)
        self.pub_sensor_json.publish(json_str)

        def _post_request():
            try: requests.post(self.SERVER_URL, json=payload, timeout=2.0)
            except Exception: pass 
        threading.Thread(target=_post_request, daemon=True).start()

    def control_loop(self):
        self.send_data_to_server()

        status_msg = String()
        status_msg.data = f"Mode: {self.state} | Bat: {self.battery_percent:.1f}% | Lux: {self.current_lux:.1f} | Temp: {self.current_temp:.1f}°C"
        self.pub_status.publish(status_msg)

        if self.state == "EXPLORING":
            if time.time() - self.last_record_time > 3.0:
                self.record_current_spot()
                self.last_record_time = time.time()
        elif self.state == "POWER_SAVING":
            self.update_charging_strategy()

    def record_current_spot(self):
        if not self.is_calibrated: return 
        pose = self.get_current_pose()
        if pose:
            self.memory_spots.append({
                'x': pose[0], 'y': pose[1], 'lux': self.current_lux,  
                'temp': self.current_temp, 'time': time.time()
            })

    def check_battery_status(self):
        if not self.is_low_battery_mode:
            if self.battery_percent <= 45.0:
                self.is_low_battery_mode = True
                self.state = "POWER_SAVING"
                self.control_lidar(False)
        else:
            if self.battery_percent >= 80.0:
                self.is_low_battery_mode = False
                self.state = "EXPLORING"
                self.control_lidar(True)

    def control_lidar(self, turn_on):
        try:
            if turn_on and not self.lidar_running:
                subprocess.Popen(["ros2", "launch", "turtlebot3_bringup", "robot.launch.py"])
                self.lidar_running = True
            elif not turn_on and self.lidar_running:
                os.system("pkill -f lds")
                self.lidar_running = False
        except Exception: pass

    def update_charging_strategy(self):
        pose = self.get_current_pose()
        if pose:
            best_spot = self.optimizer.find_best_spot((pose[0], pose[1]), self.memory_spots)
            if best_spot and best_spot['final_score'] > 0:
                self.get_logger().info(f"🚀 최적 충전지 발견! 점수: {best_spot['final_score']:.2f}")
                self.state = "MOVING_TO_CHARGE"
        else:
            self.get_logger().warn("위치 인식 불가 (SLAM 미구동).")

def main(args=None):
    rclpy.init(args=args)
    node = MarsRoverController()
    try: rclpy.spin(node)
    except KeyboardInterrupt: pass
    finally:
        if hasattr(node, 'ser') and node.ser.is_open: node.ser.close()
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
