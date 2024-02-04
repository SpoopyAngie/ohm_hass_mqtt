from platform import uname
from os import path as os_path
from time import sleep
from re import sub as regex_substitute
from json import dumps as json_dumps
from yaml import safe_load as yaml_safe_load
import paho.mqtt.client as mqtt
from clr import AddReference as clr_add_reference
from pyuac import main_requires_admin

def make_string_safe(input_string): return regex_substitute(r'[^a-zA-Z0-9-]', '', input_string.replace(" ", "-")).lower()

clr_add_reference(f"{os_path.dirname(os_path.abspath(__file__))}\OpenHardwareMonitorLib.dll")
from OpenHardwareMonitor import Hardware

hostname = uname()[1]
computer_name = hostname

hass_data_types = {
    # https://www.home-assistant.io/integrations/sensor/#device-class
    "Temperature": {
        "device_class": "temperature",
        "unit_of_measurement": "ºC",
        "icon": "mdi:thermometer",
        "value_template": "{{ value_json.value | round(1) }}"
    },
    "Power": {
        "device_class": "power",
        "unit_of_measurement": "W",
        "icon": "mdi:lightning-bolt",
        "value_template": "{{ value_json.value | round(1) }}"
    },
    "Fan": {
        # "device_class": "none",
        "unit_of_measurement": "RPM",
        "icon": "mdi:fan",
        "value_template": "{{ value_json.value | round(0) }}"
    },
    "Clock": {
        "device_class": "frequency",
        "unit_of_measurement": "Mhz",
        "icon": "mdi:chip",
        "value_template": "{{ value_json.value | round(1) }}"
    },
    "Voltage": {
        "device_class": "voltage",
        "unit_of_measurement": "mV",
        "icon": "mdi:lightning-bolt",
        "value_template": "{{ value_json.value | round(3) }}"
    },
    "Load": {
        # "device_class": "none",
        "unit_of_measurement": "%",
        "icon": "mdi:chip",
        "value_template": "{{ value_json.value | round(1) }}"
    },
    "Data": {
        "device_class": "data_size",
        "unit_of_measurement": "GB",
        "icon": "mdi:harddisk",
        "value_template": "{{ value_json.value | round(1) }}"
    },
    "Control": {
        # "device_class": "none",
        "unit_of_measurement": "",
        # "icon": "mdi:chip",
        "value_template": "{{ value_json.value }}"
    }
}

def get_sensor_unique_id(component, sensor): return make_string_safe(f"{hostname} {component.get_Identifier()} {sensor.get_Name()} {sensor.get_SensorType()}")

@main_requires_admin
def main():
    computer = Hardware.Computer()
    computer.set_CPUEnabled(True)
    computer.set_FanControllerEnabled(False)
    computer.set_GPUEnabled(True)
    computer.set_HDDEnabled(True)
    computer.set_MainboardEnabled(True)
    computer.set_RAMEnabled(True)
    computer.Open()

    configuration_file = open(f"{os_path.dirname(os_path.abspath(__file__))}\configuration.yaml")
    configuration = yaml_safe_load(configuration_file)
    
    client = mqtt.Client(hostname)
    client.username_pw_set(str(configuration["mqtt"]["username"]), str(configuration["mqtt"]["password"]))
    client.connect(str(configuration["mqtt"]["address"]), int(configuration["mqtt"]["port"]), 60)
    # client.on_connect = print
    # client.on_disconnect = print
    # client.on_publish = print
    # client.on_publish = print
    client.loop_start()

    for component in computer.Hardware:
        ## ['Accept', 'Equals', 'GetHashCode', 'GetReport', 'GetType', 'HardwareType', 'Identifier', 'Name', 'Parent', 'SensorAdded', 'SensorRemoved', 'Sensors', 'SubHardware', 'ToString', 'Traverse', 'Update', '__class__', '__delattr__', '__dir__', '__doc__', '__eq__', '__format__', '__ge__', '__getattribute__', '__gt__', '__hash__', '__init__', '__init_subclass__', '__le__', '__lt__', '__module__', '__ne__', '__new__', '__reduce__', '__reduce_ex__', '__repr__', '__setattr__', '__sizeof__', '__str__', '__subclasshook__', 'add_SensorAdded', 'add_SensorRemoved', 'get_HardwareType', 'get_Identifier', 'get_Name', 'get_Parent', 'get_Sensors', 'get_SubHardware', 'remove_SensorAdded', 'remove_SensorRemoved', 'set_Name']
        component.Update()

        for sensor in component.get_Sensors():
            ## ['Accept', 'Control', 'Equals', 'GetHashCode', 'GetType', 'Hardware', 'Identifier', 'Index', 'IsDefaultHidden', 'Max', 'Min', 'Name', 'Parameters', 'ResetMax', 'ResetMin', 'SensorType', 'ToString', 'Traverse', 'Value', 'Values', '__class__', '__delattr__', '__dir__', '__doc__', '__eq__', '__format__', '__ge__', '__getattribute__', '__gt__', '__hash__', '__init__', '__init_subclass__', '__le__', '__lt__', '__module__', '__ne__', '__new__', '__reduce__', '__reduce_ex__', '__repr__', '__setattr__', '__sizeof__', '__str__', '__subclasshook__', 'get_Control', 'get_Hardware', 'get_Identifier', 'get_Index', 'get_IsDefaultHidden', 'get_Max', 'get_Min', 'get_Name', 'get_Parameters', 'get_SensorType', 'get_Value', 'get_Values', 'set_Name']
            if not sensor.get_IsDefaultHidden():
                sensor_unique_id = get_sensor_unique_id(component, sensor)
                topic = f"homeassistant/sensor/{sensor_unique_id}/config"
                data = {
                    "unique_id": sensor_unique_id,
                    "state_topic": f"homeassistant/sensor/{sensor_unique_id}/state",
                    "name": f"({hostname}) {component.get_Name()} - {sensor.get_Name()} {sensor.get_SensorType()}",
                }

                if str(sensor.get_SensorType()) in hass_data_types:
                    client.publish(topic, json_dumps({**data, **hass_data_types[str(sensor.get_SensorType())]}))
                else:
                    print(f"{sensor_unique_id}: No config for '{sensor.get_SensorType()}'")

    while True:
        sleep(5)

        if not client.is_connected():
            print("Attempt to reconnect ...")
            client.reconnect()
            pass

        for component in computer.Hardware:
            component.Update()
            for sensor in component.get_Sensors():
                if not sensor.get_IsDefaultHidden():
                    sensor_unique_id = get_sensor_unique_id(component, sensor)
                    topic = f"homeassistant/sensor/{sensor_unique_id}/state"
                    data = {"value": sensor.get_Value()}
                    client.publish(topic, json_dumps(data))

if __name__ == "__main__":
    main()