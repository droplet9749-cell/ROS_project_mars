# ROS_project_mars
Mars_explore_robot(charging_algorithm)

## Project Structure

- arduino/ : Sensor data acquisition (CDS, IMU)
- python/  : Serial parsing and DB storage
- db/      : Database schema and queries

## Serial Permission
```bash
sudo usermod -a -G dialout $USER
reboot
```

## 🚀 Project Presentation

> ROS2 기반 알약 배송 로봇 시스템 발표 자료

[![presentation](./ROS_project_mars/preview.png)](./ROS_project_mars/MARS_PROJECT_final.pdf)
