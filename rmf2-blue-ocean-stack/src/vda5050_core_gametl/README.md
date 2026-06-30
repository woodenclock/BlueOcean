# VDA5050 Library and Support Tools

This repository provides libraries and tools to
- Enable VDA5050 compatibility for AGV/AMRs
- Build custom VDA5050 Master.

> **Upstream routing:** this library does not plan routes. The master is
> designed to receive its route/order (the node + edge graph) from an **RMF2
> MAPF Plan Executor and Plan server** upstream; the master then validates,
> stitches, delivers, and tracks that order over VDA5050.

# Build and install 
```bash 
colcon build 
echo "source ${PWD}/install/setup.bash" >> ~/.bashrc
```

# Run C++ Adapter
```bash
ros2 run vda5050_core adapter_example tcp://localhost:1883 my_agv
```
# Run Blue Ocean demo adapters
MQTT order -> VDA5050-Adapter-CPP -> Python-Bindings -> bridge spellbook -> robot REST API
```bash 
cd vda5050_core

# build the vda5050, this will install the vda5050_core_py to your default python3
colcon build --symlink-install
```

```bash 
## Terminal 1
# start the demo adapter (from demo-june-blue-ocean/)
cd vda5050_core_py/demo-june-blue-ocean
python3 example_autoxing_adapter_client.py

## Terminal 2
# publish a demo MQTT order (from the umbrella repo root)
uv run fixtures/run_publish_mqtt_route.py
```


# Troubleshoot 
if fail try adding `Add: [-std=c++17]` to the .clangd compileFlag

  