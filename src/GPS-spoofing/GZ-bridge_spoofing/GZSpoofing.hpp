#ifndef GZSPOOF_HPP
#define GZSPOOF_HPP

#include <string>
#include <memory>
#include <gz/msgs.hh>
#include <gz/transport.hh>

class GZSpoof
{
public:
    double distance_travelled = 0.0;
    double attack_start_distance;

    GZSpoof(const std::string &world, const std::string &model_name, const std::string &attack_type, double attack_start_distance);
    ~GZSpoof();

    // Initialize the spoofing system
    void initialize();

    double calculateDistance(double lat1, double lon1, double lat2, double lon2);
    double* getAttackBias(double distance_travelled, const std::string &attack_type);    

    bool subscribeNavsat();
    void navSatCallback(const gz::msgs::NavSat &msg);

private:
    bool _initialized;
    bool _active = false;
    std::string _world_name;
    std::string _model_name;
    std::string _attack_type;

    gz::transport::Node _node;
    gz::transport::Node::Publisher _pub;
    double _prev_pos[3];
    bool _prev_pos_set = false;
    int _msg_count;
};

#endif // GZSpoof_HPP