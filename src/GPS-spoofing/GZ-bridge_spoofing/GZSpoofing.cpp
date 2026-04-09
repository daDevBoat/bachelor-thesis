/**
 * @file filename.cpp
 * @brief Handles all the spoofing logic for the GPS data in Gazebo, including subscribing to the NavSat topic, applying the spoofing attack, and publishing the modified data.
 * @date 2026-04
 */


 /*
 change this one line inside the subscribeNavsat() function to subscribe TO:
 std::string nav_sat_topic = "/world/custom_gps/spoofed_navsat";
 SHOULD BE line 309 in GZBridge.cpp

 to run this script, use the following commands in the terminal:
 
 make
 ./GZSpoofing default x500_depth_0 constant 50

 start this before gz with PX4
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
GZSpoof::GZSpoof(const std::string &world, const std::string &model_name, const std::string &attack_type, double start_distance_attack) {
    _world_name = world;
    _model_name = model_name;
    _attack_type = attack_type;
    attack_start_distance = start_distance_attack;

    gz::transport::AdvertiseOptions pubOpts;

    _pub = _node.Advertise<gz::msgs::NavSat>("/world/custom_gps/spoofed_navsat");
}

GZSpoof::~GZSpoof() {
    // Destructor
}

void GZSpoof::initialize() {
    //GZSpoof::subscribeClock();

    // We must wait for clock before subscribing to other topics. This is because
	// if we publish a 0 timestamp it screws up the EKF.
    /*
	while (1) {
		std::this_thread::sleep_for(std::chrono::seconds(3));

		if (_realtime_clock_set) {
			std::this_thread::sleep_for(std::chrono::seconds(3));
			break;
		}
	}
    */
    GZSpoof::subscribeNavsat();
    _initialized = true;
}

bool GZSpoof::subscribeNavsat()
{
	std::string nav_sat_topic = "/world/" + _world_name + "/model/" + _model_name +
				    "/link/base_link/sensor/navsat_sensor/navsat";

    cout << "Subscribing to NavSat topic: " << nav_sat_topic << endl;

    gz::transport::SubscribeOptions opts;
    //opts.SetMsgsPerSec(1);

	if (!_node.Subscribe(nav_sat_topic, &GZSpoof::navSatCallback, this, opts)) {
		cout << "Failed to subscribe to NavSat topic: " << nav_sat_topic << endl;
		return false;
	}
	return true;
}

bool GZSpoof::subscribeClock()
{
	std::string clock_topic = "/world/" + _world_name + "/clock";

	if (!_node.Subscribe(clock_topic, &GZSpoof::clockCallback, this)) {
		cout << "Failed to subscribe to clock topic: " << clock_topic << endl;
		return false;
	}

	return true;
}

void GZSpoof::clockCallback(const gz::msgs::Clock &msg)
{
	// NOTE: PX4-SITL time needs to stay in sync with gz, so this clock-sync will happen on every callback.

	//_current_sim_time.mutable_stamp()->set_sec(msg.sim().sec());
    //_current_sim_time.mutable_stamp()->set_nsec(msg.sim().nsec());
}

void GZSpoof::navSatCallback(const gz::msgs::NavSat &msg)
{

    //auto seconds = std::chrono::duration_cast<std::chrono::seconds>(_current_sim_time).count();
    //auto nanos = std::chrono::duration_cast<std::chrono::nanoseconds>(_current_sim_time - std::chrono::seconds(seconds)).count();

    //spoofed_msg.mutable_header()->mutable_stamp()->set_sec(seconds);
    //spoofed_msg.mutable_header()->mutable_stamp()->set_nsec(nanos);

	double latitude = msg.latitude_deg();
	double longitude = msg.longitude_deg();
	double altitude = msg.altitude();

    if (!_prev_pos_set) {
        _prev_pos[0] = latitude;
        _prev_pos[1] = longitude;
        _prev_pos[2] = altitude;
        _prev_pos_set = true;
    } 

    distance_travelled += calculateDistance(_prev_pos[0], _prev_pos[1], latitude, longitude);  
    
    _prev_pos[0] = latitude;
    _prev_pos[1] = longitude;
    _prev_pos[2] = altitude;

    double* bias = getAttackBias(distance_travelled, _attack_type);

	gz::msgs::NavSat spoofed_msg = msg; // Start with the original message and modify it
    spoofed_msg.set_latitude_deg(latitude + bias[0]); // Spoofed latitude
    spoofed_msg.set_longitude_deg(longitude + bias[1]); // Spoofed longitude
    spoofed_msg.set_altitude(altitude + bias[2]); // Spoofed altitude

    _pub.Publish(spoofed_msg);

    if (_msg_count % 25 == 0) {
        cout << "Received NavSat: lat = " << latitude << ", lon = " << longitude << ", alt = " << altitude << endl;
        cout << "Current attack bias: lat = " << bias[0] << ", lon = " << bias[1] << ", alt = " << bias[2] << endl;
        cout << "Published spoofed NavSat: lat = " << spoofed_msg.latitude_deg() << ", lon = " << spoofed_msg.longitude_deg() << ", alt = " << spoofed_msg.altitude() << endl;
        cout << "Total distance travelled: " << distance_travelled << " meters" << endl;
        //cout << "Latency: " << (gz::msgs::Convert(msg.header().stamp()) - current_time) << endl;
    }
    
    _msg_count++;
}

double* GZSpoof::getAttackBias(double distance_travelled, const std::string &attack_type) {
    static double bias[3] = {0.0, 0.0, 0.0}; // lat, lon, alt bias

    if (distance_travelled < attack_start_distance) {
        return bias; // No bias before attack start distance
    }

    if (!_active) {
        cout << attack_type << " attack activated at distance: " << distance_travelled << " meters" << endl;
        _active = true;
    }

    if (attack_type == "constant") {
        bias[0] = 0.001;
        bias[1] = 0.001; 
    } else if (attack_type == "increasing") {
        bias[0] = 0.00001 * distance_travelled; // Increases with distance
        bias[1] = 0.00001 * distance_travelled; // Increases with distance
    } else if (attack_type == "random") {
        bias[0] = ((double)rand() / RAND_MAX - 0.5) * 0.0002; // Random between -10 and +10 meters
        bias[1] = ((double)rand() / RAND_MAX - 0.5) * 0.0002; // Random between -10 and +10 meters
    }

    return bias;
}

double GZSpoof::calculateDistance(double lat1, double lon1, double lat2, double lon2) {
    // Haversine formula to calculate distance between two GPS coordinates
    const double R = 6371e3; // Earth radius in meters
    double phi1 = lat1 * M_PI / 180.0;
    double phi2 = lat2 * M_PI / 180.0;
    double delta_phi = (lat2 - lat1) * M_PI / 180.0;
    double delta_lambda = (lon2 - lon1) * M_PI / 180.0;

    double a = sin(delta_phi / 2) * sin(delta_phi / 2) +
               cos(phi1) * cos(phi2) *
               sin(delta_lambda / 2) * sin(delta_lambda / 2);
    double c = 2 * atan2(sqrt(a), sqrt(1 - a));

    return R * c; // Distance in meters
}


int main(int argc, char* argv[]) {

    if (argc != 5) {
        std::cerr << "Usage: " << argv[0] << " <world_name> <model_name> <attack_type> <attack_start_distance>" << std::endl;
        exit(1);
    }

    std::string world_name = std::string(argv[1]);
    std::string model_name = std::string(argv[2]);
    std::string attack_type = std::string(argv[3]);
    double distance_attack_start = std::stod(argv[4]);

    GZSpoof spoofer(world_name, model_name, attack_type, distance_attack_start);

    spoofer.initialize();
    try {
        while (true) {
            //Keep the main thread alive to allow callbacks to be processed
            //std::this_thread::sleep_for(std::chrono::seconds(1));
            /*
            if (std::cin.rdbuf()->in_avail() > 0) {
                std::string input;
                std::getline(std::cin, input);
                if (input == "start") {
                    spoofer.attack_start_distance = 0;
                    cout << "Spoofing attack started immediately" << endl;
                }
            }
            */
        }
        return 0;
    } catch (const std::exception& e) {
        std::cerr << "Error: " << e.what() << std::endl;
        exit(1);
    }
}