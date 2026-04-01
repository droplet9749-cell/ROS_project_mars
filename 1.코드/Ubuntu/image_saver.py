#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import CompressedImage
import cv2
import numpy as np
import os
import time

class ImageSaverNode(Node):
    def __init__(self):
        super().__init__('image_saver_node')
        
        # 1. 사진을 저장할 폴더 설정 (홈 디렉토리 아래 mars_dataset 생성)
        self.save_dir = os.path.expanduser('~/mars_dataset')
        if not os.path.exists(self.save_dir):
            os.makedirs(self.save_dir)
            
        # 2. 촬영 파라미터 설정
        self.save_interval = 1.0  # 🌟 1.0초마다 한 장씩 저장 (너무 많으면 2.0으로 늘려도 됩니다)
        self.last_save_time = time.time()
        self.image_count = 0
        
        # 3. 카메라 토픽 구독 (라즈베리파이에서 넘어오는 압축 이미지)
        self.subscription = self.create_subscription(
            CompressedImage,
            '/image_raw/compressed',
            self.image_callback,
            10)
        
        self.get_logger().info(f"📸 마스 탐사선 사진 촬영 요원 투입! 저장 위치: {self.save_dir}")

    def image_callback(self, msg):
        current_time = time.time()
        
        # 설정한 간격(예: 1초)이 지났을 때만 사진을 저장합니다.
        if current_time - self.last_save_time >= self.save_interval:
            try:
                # ROS 2 압축 이미지를 OpenCV 이미지로 변환 (가장 빠르고 에러 없는 방식)
                np_arr = np.frombuffer(msg.data, np.uint8)
                cv_image = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
                
                if cv_image is not None:
                    # 파일 이름 생성 (예: mars_0000.jpg, mars_0001.jpg)
                    filename = os.path.join(self.save_dir, f"mars_{self.image_count:04d}.jpg")
                    cv2.imwrite(filename, cv_image)
                    
                    self.get_logger().info(f"✅ 사진 저장 완료: {filename}")
                    
                    self.image_count += 1
                    self.last_save_time = current_time
                else:
                    self.get_logger().warn("⚠️ 이미지 디코딩 실패!")
                    
            except Exception as e:
                self.get_logger().error(f"❌ 오류 발생: {e}")

def main(args=None):
    rclpy.init(args=args)
    node = ImageSaverNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info("\n🛑 탐사 종료! 사진 촬영을 마칩니다.")
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()

if __name__ == '__main__':
    main()
