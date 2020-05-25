# Compatibility module for DS18B20+ One Wire Digital Temperature Sensor
# By Lexi Stevens

import os  # Used for enabling two interface drivers on Raspbian

# Emulation mode
# Change this to true for testing purposes and/or if not on the server environment
# You can also change the emulation_temperature variable
emulation_mode = False
emulation_temperature = 19

# Sensor serial
# Enter the serial code of the temperature sensor
# Can be found at sys/bus/w1/devices/<serial_here>
sensor_serial = "28-00000623003b"

sensor_file_path = "/sys/bus/w1/devices/" + sensor_serial + "/w1_slave"

# File content example:
# 72 01 4b 46 7f ff 0e 10 57 : crc=57 YES
# 72 01 4b 46 7f ff 0e 10 57 t=23125


def read_raw_lines(file_path):
    file_object = open(file_path, "r")
    lines = file_object.readlines()
    file_object.close()
    return lines


def check_reading(lines):
    if lines[0].strip()[-3:] == 'YES':
        return True
    else:
        return False


def strip_lines(lines):
    value = lines[1].find('t=')
    if value != -1:
        string = lines[1].strip()[value + 2:]
        return int(string)


def convert_temp_value(value):
    temperature = float(value) / 1000.0
    return temperature


def get_temperature():
    if emulation_mode:
        current_temperature = emulation_temperature
    else:
        os.system('modprobe w1-gpio')
        os.system('modprobe w1-therm')
        lines = read_raw_lines(sensor_file_path)
        if check_reading(lines):
            value = strip_lines(lines)
            current_temperature = convert_temp_value(value)
        else:
            current_temperature = False
    return current_temperature
