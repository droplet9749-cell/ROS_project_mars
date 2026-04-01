import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import serial
import json

class EnvNode(Node):

    def __init__(self):
        super().__init__('env_node')

        self.pub = self.create_publisher(String, 'env_data', 10)

        self.ser = serial.Serial('/dev/ttyACM0',115200,timeout=1)
        # USB Serial 통신
        
        # serial.Serial('/dev/ttyS0',115200,timeout=1)
        # UART Serial 통신+ import os
        # PORT = os.getenv("OPENCR_PORT","/dev/ttyACM0")

        self.timer = self.create_timer(0.5, self.loop)

    def loop(self):

        try:
            line = self.ser.readline().decode().strip()

            if not line.startswith("{"):
                return

            data = json.loads(line)

            msg = String()
            msg.data = json.dumps(data)

            self.pub.publish(msg)

            self.get_logger().info(f"Publish: {msg.data}")

        except Exception as e:
            self.get_logger().error(str(e))


def main():
    print("env node running")
    rclpy.init()
    node = EnvNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
