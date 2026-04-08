/**
 * @file filename.cpp
 * @brief Brief description of what this file does
 * @author Your Name
 * @date YYYY-MM-DD
 */

#include <iostream>
#include <vector>
#include <string>
#include <memory>
#include "GZSpoofing.hpp"



// Using declarations (use sparingly in header files)
using std::cout;
using std::endl;


// Constructor
GZSpoof::GZSpoof(const std::string &world, const std::string &model_name) {
    _world_name = world;
    _model_name = model_name;
    _pub = _node.Advertise<gz::msgs::NavSat>("/world/custom_gps/spoofed_navsat");
}

GZSpoof::~GZSpoof() {
    // Destructor
}

void GZSpoof::initialize() {
    GZSpoof::subscribeNavsat();
    _initialized = true;
}

bool GZSpoof::subscribeNavsat()
{
	std::string nav_sat_topic = "/world/" + _world_name + "/model/" + _model_name +
				    "/link/base_link/sensor/navsat_sensor/navsat";

    cout << "Subscribing to NavSat topic: " << nav_sat_topic << endl;

	if (!_node.Subscribe(nav_sat_topic, &GZSpoof::navSatCallback, this)) {
		cout << "Failed to subscribe to NavSat topic: " << nav_sat_topic << endl;
		return false;
	}
	return true;
}

void GZSpoof::navSatCallback(const gz::msgs::NavSat &msg)
{
	double latitude = msg.latitude_deg();
	double longitude = msg.longitude_deg();
	double altitude = msg.altitude();

	gz::msgs::NavSat spoofed_msg = msg; // Start with the original message and modify it
    spoofed_msg.set_latitude_deg(latitude); // Spoofed latitude
    spoofed_msg.set_longitude_deg(longitude); // Spoofed longitude
    spoofed_msg.set_altitude(altitude); // Spoofed altitude

    _pub.Publish(spoofed_msg);

    if (_msg_count % 25 == 0) {
        cout << "Received NavSat: lat = " << latitude << ", lon = " << longitude << ", alt = " << altitude << endl;
        cout << "Published spoofed NavSat: lat = " << spoofed_msg.latitude_deg() << ", lon = " << spoofed_msg.longitude_deg() << ", alt = " << spoofed_msg.altitude() << endl;
    }
    
    _msg_count++;
}


// Free functions
int main(int argc, char* argv[]) {
    std::string world_name = std::string(argv[1]);
    std::string model_name = std::string(argv[2]);
    GZSpoof spoofer(world_name, model_name);

    spoofer.initialize();
    try {
        while (true) {
            //Keep the main thread alive to allow callbacks to be processed
            std::this_thread::sleep_for(std::chrono::seconds(1));
        }
        return 0;
    } catch (const std::exception& e) {
        std::cerr << "Error: " << e.what() << std::endl;
        return 1;
    }
}