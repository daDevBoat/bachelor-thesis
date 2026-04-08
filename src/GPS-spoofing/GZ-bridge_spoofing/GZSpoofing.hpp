#ifndef GZSPOOF_HPP
#define GZSPOOF_HPP

#include <string>
#include <memory>
#include <gz/msgs.hh>
#include <gz/transport.hh>

class GZSpoof
{
public:
    GZSpoof(const std::string &world, const std::string &model_name);
    ~GZSpoof();

    // Initialize the spoofing system
    void initialize();

    // Start spoofing GPS signals
    bool startSpoofing();

    // Stop spoofing GPS signals
    bool stopSpoofing();

    bool subscribeNavsat();
    void navSatCallback(const gz::msgs::NavSat &msg);

private:
    bool _initialized;
    bool _active;
    std::string _world_name;
    std::string _model_name;
    gz::transport::Node _node;
    gz::transport::Node::Publisher _pub;
    int _msg_count;
};

#endif // GZSpoof_HPP