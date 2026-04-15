// Copyright 2016 Open Source Robotics Foundation, Inc.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

#include <memory>

#include "rclcpp/rclcpp.hpp"
#include "px4_msgs/msg/vehicle_global_position.hpp" // Input topic
#include "px4_msgs/msg/sensor_gps.hpp"           // Output topic

class GpsSpoofer : public rclcpp::Node
{
public:
  GpsSpoofer()
  : Node("spoofer")
  {
    auto qos = rclcpp::SensorDataQoS();     // Quality of Service
    subscription_ =
      this->create_subscription<px4_msgs::msg::VehicleGlobalPosition>("/fmu/out/vehicle_global_position", qos, 
        std::bind(
        &GpsSpoofer::gps_callback, // Func address
        this,                      // The owner (instance) of the call
        std::placeholders::_1      // Placeholde waiting for data
));

  }

private:
  void gps_callback(const px4_msgs::msg::VehicleGlobalPosition::SharedPtr msg)
  {
    //auto spoofed_msg = px4_msgs::msg::SensorGps();
    
    /*
    spoofed_msg.timestamp = this->get_clock()->now().nanoseconds() / 1000;
    spoofed_msg.lat = msg->lat + 1000; // ADD BIAS: Shift latitude by ~10 meters
    spoofed_msg.lon = msg->lon;
    spoofed_msg.alt = msg->alt;
    */

    RCLCPP_INFO(this->get_logger(), "The drones REAL GPS POS\n Lat: %f, Lon: %f, Alt: %f", msg->lat, msg->lon, msg->alt);
    
    //publisher_->publish(spoofed_msg);
  }

private:
  rclcpp::Subscription<px4_msgs::msg::VehicleGlobalPosition>::SharedPtr subscription_;
};

int main(int argc, char * argv[])
{
  rclcpp::init(argc, argv);
  rclcpp::spin(std::make_shared<GpsSpoofer>());
  rclcpp::shutdown();
  return 0;
}
