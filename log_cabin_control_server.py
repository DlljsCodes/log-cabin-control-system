# Log Cabin Control System
# By Lexi Stevens

# Import libraries
# (Must be installed to Python environment)
import time  # Used for pausing
from datetime import datetime  # Used for getting the current date & time
from flask import Flask, jsonify, request, abort  # Used for receiving REST API calls and sending responses
import logging  # Used for recording program debug output into a file and console
import threading  # Used for detecting REST API calls alongside running the rest of the program
import os  # Used for getting the file path of certain directories and checking if a file exists
from darksky.api import DarkSky  # Used for getting weather data from the Dark Sky API
from darksky.types import languages, units, weather
import sqlite3  # Used for accessing the event log database
from sqlite3 import Error

# Import modules
# (Must be included in the lib directory, located in the same directory as the program, as "<module_name>.py")
from lib import tempsensor  # Used for getting the current temperature from the temperature sensor (Written by me)
from lib import cabinblinds  # Used for moving the blind servo motors (Supplied by client)
from lib import energenie  # Used for setting the heater and devices, and getting presence detection from the motion sensor (Supplied by client)
from lib import lightsensor  # Used for getting light level values from the light sensor (Written by me)


# Set up and start logging
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter(fmt="[%(asctime)s] [%(levelname)s] %(message)s",
                              datefmt="%d/%m/%Y %H:%M:%S")

# File handler
fh = logging.FileHandler("cabin_control.log")
fh.setLevel(logging.DEBUG)
fh.setFormatter(formatter)
logger.addHandler(fh)

# Console handler
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
ch.setFormatter(formatter)
logger.addHandler(ch)

logger.info("Starting Log Cabin Control System...")

# Define global variables and constants
# Main code loop
cycle_count = 0  # How many main code loops have been performed (int)
emulation = False

# Heating
auto_heating = False  # If the heating should be automatically changed (bool)
heating_mode = "off"  # The heating mode set in the interface (to be depreciated, use auto_heating instead,
# unless interacting with control interface) (str)
desired_temp = 20.0  # The desired temperature that should be maintained (float)
desired_temp_upper = 20.5  # The upper margin of the desired temperature (float)
desired_temp_lower = 19.5  # The lower margin of the desired temperature (float)
DESIRED_TEMP_UPPER_BOUND = 30  # The upper bound of the desired temperature (int)
DESIRED_TEMP_LOWER_BOUND = 15  # The lower bound of the desired temperature (int)
DESIRED_TEMP_INCREMENT = 0.5  # How much to increment or decrement the desired temperature by (float)
DESIRED_TEMP_MARGIN = 0.5  # How much to deviate the desired temperature by when checking the actual temperature (float)
HeaterObject = energenie.device(socket_number=1, logger=logger)  # The object to control the heater

# Devices
auto_presence = True  # If the devices should be automatically turned on (bool)
PRESENCE_TIMEOUT = 30
DevicesObject = energenie.device(socket_number=2, logger=logger)  # The object to control the devices
CABIN_PIR = 19    # The GPIO pin of the motion sensor (physical pin 35) (int)
MotionSensorObject = energenie.GPIOInputDevice(CABIN_PIR, presence_interrupt)

# Blinds
auto_blinds = True  # If the blinds should be automatically be open and closed (bool)
CLOUD_COVER_THRESHOLD = 0.5  # The threshold of the percentage cloud cover (float)
TEMPERATURE_THRESHOLD = 20  # The threshold of the maximum temperature of the day (int)
LIGHT_LEVEL_THRESHOLD = 1200000  # The threshold of the light level outside (float)
CABIN_LOCATION = {"LATITUDE": 51.456857, "LONGITUDE": -1.053791}  # The location of the cabin (dict{float})
LightSensorObject = lightsensor.LightSensor(logger=logger, gain="low")  # The object to receive data from the light sensor


blind_objects = {  # List of objects to control the blinds
    "left": cabinblinds.blindservo("left", 0, logger, simulation=emulation),
    "leftdoor": cabinblinds.blindservo("leftdoor", 1, logger, simulation=emulation),
    "rightdoor": cabinblinds.blindservo("rightdoor", 2, logger, simulation=emulation),
    "right": cabinblinds.blindservo("right", 3, logger, simulation=emulation)}

# Miscellaneous
app = Flask(__name__)  # Flask app initialisation
BIND = "0.0.0.0"
PORT = 7890
app_thread = threading.Thread(target=app.run, kwargs={"host":BIND,"port":PORT}, name="cabinapi", daemon=True)  # Flask app thread
use_darksky_api = False  # If Dark Sky API functions should be used or not (bool)
DARKSKY_API_KEY_FILE_NAME = "darksky_api_key.txt"  # The file name of the Dark Sky API key file (str)
API_KEY = ""  # The secret key used to access the Dark Sky API, obtained from the above file (str)
use_database = False  # If event log database functions should be used or not (bool)
DATABASE_FILE_NAME = "event_log.db"  # The file name of the event log database (str)
# The following are keyword constants to improve readability of the code
ON = True
OFF = False
OPEN = 10
CLOSED = 20


# Define subroutines
# Main code loop
def main_loop():
    # Get global variable
    global cycle_count

    # Execute subroutines
    logger.debug("Running heating module")
    heating()  # Heating Module
    logger.debug("Running devices module")
    devices()  # Devices Module
    logger.debug("Running blinds module")
    blinds()   # Blinds Module

    # Increase cycle count and wait
    cycle_count += 1  # Increase cycle count by one
    logger.debug(f"Cycle count is now {cycle_count}")
    logger.debug("Waiting 1 minute")
    time.sleep(60)  # Wait 1 minute


# Heating subroutine
def heating():
    # Get global variables
    global auto_heating, desired_temp_upper, desired_temp_lower

    # Only run this if heating is set to auto
    if auto_heating:
        logger.debug("Auto heating is true, running")

        # Obtain current temperature
        logger.debug("Getting temperature")
        temp = tempsensor.get_temperature()
        if not temp:  # In case there was a problem with the sensor
            logger.warning("Problem getting current temperature from sensor")
            logger.debug("Skipping...")
        else:
            current_temperature = temp
            logger.debug(f"Current temperature: {current_temperature}")
            logger.debug(f"Desired temperature: {desired_temp}")

            # Choose action to perform
            state = HeaterObject.get_state()
            logger.debug(f"Heating state: {state}")
            if state is ON and current_temperature > desired_temp_upper:
                logger.debug("Turning heating off")  # Turn the heating off
                HeaterObject.switch(OFF)
                write_event("TEMPABV", str(current_temperature), "HEATSTA", "off", True)
            elif state is OFF and current_temperature < desired_temp_lower:
                logger.debug("Turning heating on")  # Turn the heating on
                HeaterObject.switch(ON)
                write_event("TEMPBEL", str(current_temperature), "HEATSTA", "on", True)
            else:
                logger.debug("No action needed, skipping")  # Won't need to turn on or off now

    else:
        logger.debug("Auto heating is false, skipping")


# Devices subroutine
def devices():
    # Get global variables
    global auto_presence, cycle_count

    # Only run this if presence is set to auto
    if auto_presence:
        logger.debug("Auto presence is true, running")

        # See if devices should be turned off
        if DevicesObject.get_state():
            if MotionSensorObject.get_state():
                logger.debug("Resetting cycle count back to 0")
                cycle_count = 0  # Reset cycle count
            elif cycle_count >= PRESENCE_TIMEOUT:
                logger.debug("Turning off devices")  # Turn the devices off
                DevicesObject.switch(OFF)
                write_event("PRESTMO", None, "DEVISTA", "off", True)
                logger.debug("Resetting cycle count back to 0")
                cycle_count = 0  # Reset cycle count
            else:
                logger.debug("No action needed, skipping")  # Won't need to turn off now
        else:
            logger.debug("No action needed, skipping")  # Won't need to turn off now

    else:
        logger.debug("Auto presence is false, skipping")


# Blinds subroutine
def blinds():
    # Get global variable
    global auto_blinds
    
    # Obtain current light level
    logger.debug("Getting light level")
    light_level = LightSensorObject.get_measurement("full_spectrum")
    logger.debug(f"Light level: {light_level} (full spectrum)")

    # Only run this if blinds are set to auto
    if auto_blinds:
        logger.debug("Auto blinds is true, running")

        # Obtain current time right now
        current_datetime = datetime.now()
        current_hour = current_datetime.hour
        logger.debug(f"Current date & time: {current_datetime}")
        logger.debug(f"Current hour: {current_hour}")
        
        # Perform an extra subroutine
        state_average = get_blind_state_average()
        logger.debug(f"Average state of blinds: {state_average}")
        if 7 <= current_hour < 8 and state_average < 15.5:  # 7 - 8 AM in the morning & blinds open
            logger.debug("Running blinds morning subroutine")
            blinds_morning()  # Will close blinds if successful
        elif 17 <= current_hour < 22 and state_average > 14.5:  # 5 - 10 PM in the evening & blinds closed
            logger.debug("Running blinds evening subroutine")
            blinds_evening()  # Will open blinds if successful
        else:
            logger.debug("No action needed, skipping")  # Won't need to run a subroutine right now

    else:
        logger.debug("Auto blinds is false, skipping")


# Blinds morning subroutine
def blinds_morning():
    # Get global variables
    global CLOUD_COVER_THRESHOLD, TEMPERATURE_THRESHOLD, CABIN_LOCATION, API_KEY

    # Obtain forecast, specifically cloud cover and temperature max values
    logger.debug("Getting forecast")
    forecast = weather_data(CABIN_LOCATION["LATITUDE"], CABIN_LOCATION["LONGITUDE"], API_KEY)
    cloud_cover = forecast.daily.data[0].cloud_cover
    temperature = forecast.daily.data[0].temperature_high
    logger.debug(f"Cloud cover: {cloud_cover}")
    logger.debug(f"Temperature: {temperature}")

    # Check to see if it exceeds the thresholds
    if cloud_cover < CLOUD_COVER_THRESHOLD and temperature > TEMPERATURE_THRESHOLD:
        logger.debug("Closing blinds")  # Close all the blinds
        set_all_blinds(CLOSED)
        write_event("BLNDMOR", f"{cloud_cover}, {temperature}", "BLNDSTA", "all, 20", True)
    else:
        logger.debug("No action needed, skipping")  # Don't need to open them today


# Blinds evening subroutine
def blinds_evening():
    # Get global variable
    global LIGHT_LEVEL_THRESHOLD

    # Obtain current light level
    logger.debug("Getting light level")
    light_level = LightSensorObject.get_measurement("full_spectrum")
    logger.debug(f"Light level: {light_level} (full spectrum)")

    # Check to see if it exceeds the threshold
    if light_level < LIGHT_LEVEL_THRESHOLD:
        logger.debug("Opening blinds")  # Open all the blinds
        set_all_blinds(OPEN)
        write_event("BLNDEVE", str(light_level), "BLNDSTA", "all, 10", True)
    else:
        logger.debug("No action needed, skipping")  # Don't need to close them tonight


# Desired temp change subroutine
def desired_temp_change():
    # Get global variables
    global desired_temp, desired_temp_upper, desired_temp_lower, DESIRED_TEMP_MARGIN

    desired_temp_upper = desired_temp + DESIRED_TEMP_MARGIN  # Set desired temp upper
    desired_temp_lower = desired_temp - DESIRED_TEMP_MARGIN  # Set desired temp lower


# Presence interrupt subroutine
def presence_interrupt(pin):
    # Get global variables
    global auto_presence, cycle_count
    logger.debug(f"Presence detected by motion sensor on pin {pin}")

    # Only run this if presence is set to auto
    if auto_presence:

        # See if devices should be turned on
        if not DevicesObject.get_state():
            logger.debug("Turning on devices")  # Turn the devices on
            DevicesObject.switch(ON)
            write_event("PRESDEC", None, "DEVISTA", "on", True)
        else:
            logger.debug("No action needed, skipping")  # Won't need to turn on now
        logger.debug("Resetting cycle count back to 0")
        cycle_count = 0  # Reset cycle count
    else:
        logger.debug("Auto presence is false, skipping")


# Set state of singular blind subroutine
def set_blind(selected_blind, state):
    temp = 0
    # Make sure all blinds are not active.
    logger.debug("Waiting for blinds to finish")
    for check_blind in blind_objects:
        while blind_objects[check_blind].active:
            temp += 1  # Wait if a blind is active.
            time.sleep(1)
    logger.debug(f"Setting blind {selected_blind} to position {state}")
    blind_objects[selected_blind].set_state(state)
    while blind_objects[selected_blind].active:
        temp += 1  # Wait while blind is being set.
        time.sleep(1)
    return temp


# Set state to all blinds subroutine
def set_all_blinds(state):
    logger.debug("Setting all blinds")
    for current_blind in blind_objects:  # Iterate through all blind objects
        set_blind(current_blind, state)  # Run function above


# Get average state of all blinds subroutine
def get_blind_state_average():
    blind_positions = []

    # Get all blind positions
    for current_blind in blind_objects:
        blind_positions.append(blind_objects[current_blind].state)

    # Calculate and return mean average
    average = sum(blind_positions) / 4
    return average


# Weather data collection subroutine
def weather_data(lat, long, api_key):
    darksky = DarkSky(api_key)
    logger.info("Powered by Dark Sky")
    forecast = darksky.get_forecast(
        lat, long,
        extend=False,
        lang=languages.ENGLISH,
        values_units=units.AUTO,
        exclude=[weather.ALERTS, weather.MINUTELY])
    return forecast


# Database connection subroutine
def connect_database(db_file):
    conn = None
    try:
        conn = sqlite3.connect(db_file)
    except Error as e:
        logger.error(e)
    return conn


# Database update subroutine
def create_event(conn, event):
    sql = '''INSERT INTO EventLog(TriggerCode,TriggerDetails,ResponseCode,ResponseDetails,Automated)
    VALUES(?,?,?,?,?)'''
    cur = conn.cursor()
    cur.execute(sql, event)
    return cur.lastrowid


# Database connection and update subroutine
# (Combining the two subroutines above into one)
def write_event(trigger_code, trigger_details, response_code, response_details, automated):
    if use_database:
        logger.debug("Writing event to database")  # Write event log to database
        conn = connect_database(DATABASE_FILE_NAME)
        event = (trigger_code, trigger_details, response_code, response_details, automated)
        with conn:
            create_event(conn, event)
        conn.close()


# Test API call
@app.route("/cabinapi/testme", methods=["GET"])
def testapi():
    return jsonify({"response": "OK"})  # Send OK response in JSON format


# Heating desired temperature change API call
@app.route("/cabinapi/setdesiredtemp", methods=["POST"])
def setdesiredtemp():
    logger.debug("Heating desired temperature change request received")
    logger.debug(f"Request body: {request.json}")
    response = None

    # Test for correct JSON request
    if not request.json or "action" not in request.json:
        abort(400)  # Send bad request error

    # Get global variables
    global desired_temp, DESIRED_TEMP_INCREMENT

    # Get action from request
    action = request.json["action"]

    # Select action
    if action == "increase":
        if desired_temp < DESIRED_TEMP_UPPER_BOUND:
            logger.debug("Increasing desired temperature")
            desired_temp += DESIRED_TEMP_INCREMENT
            desired_temp_change()
            write_event("APIDETM", str(desired_temp), "HEATDES", str(desired_temp), False)
        else:
            response = "Error: Temperature will exceed upper bound"
    elif action == "decrease":
        if desired_temp > DESIRED_TEMP_LOWER_BOUND:
            logger.debug("Decreasing desired temperature")
            desired_temp -= DESIRED_TEMP_INCREMENT
            desired_temp_change()
            write_event("APIDETM", str(desired_temp), "HEATDES", str(desired_temp), False)
        else:
            response = "Error: Temperature will exceed lower bound"
    elif action == "set":       
        if "desired_temp" not in request.json:
            abort(400)  # Send bad request error
        new_temp = request.json["desired_temp"]
        if DESIRED_TEMP_LOWER_BOUND < new_temp < DESIRED_TEMP_UPPER_BOUND:
            logger.debug("Setting desired temperature to value")
            desired_temp = new_temp
            desired_temp_change()
            write_event("APIDETM", str(desired_temp), "HEATDES", str(desired_temp), False)
        else:
            response = "Error: Temperature will exceed bounds"
    else:
        abort(400)  # Send bad request error
    
    if response is None:
        response = "OK"
    return jsonify({"response": response})  # Send response in JSON format


# Heating auto mode change API call
@app.route("/cabinapi/setheatingmode", methods=["POST"])
def setheatingmode():
    logger.debug("Heating auto mode change request received")
    logger.debug(f"Request body: {request.json}")

    # Test for correct JSON request
    if not request.json or "mode" not in request.json:
        abort(400)  # Send bad request error

    # Get global variables
    global auto_heating, heating_mode

    # Get mode from request
    mode = request.json["mode"]

    # Comparison and action
    if mode == "auto":
        logger.debug("Setting auto mode to on")
        auto_heating = ON
        write_event("APIHEMO", mode, "HEATMOD", "on", False)
    elif mode == "manual":
        logger.debug("Setting auto mode to off")
        auto_heating = OFF
        write_event("APIHEMO", mode, "HEATMOD", "off", False)
    elif mode == "off":
        logger.debug("Setting auto mode to off")
        auto_heating = OFF
        write_event("APIHEMO", mode, "HEATMOD", "off", False)
        logger.debug("Turning heating off")
        HeaterObject.switch(OFF)
        write_event("APIHEMO", mode, "HEATSTA", "off", False)
    else:
        abort(400)  # Send bad request error

    # Set value from request to global variable
    heating_mode = mode

    return jsonify({"response": "OK"})  # Send OK response in JSON format


# Heating state change API call
@app.route("/cabinapi/setheatingstatus", methods=["POST"])
def setheatingstatus():
    logger.debug("Heating state change request received")
    logger.debug(f"Request body: {request.json}")

    # Test for correct JSON request
    if not request.json or "status" not in request.json:
        abort(400)  # Send bad request error

    # Get status from request
    status = request.json["status"]

    # Check if bool and set value
    if status is True:
        logger.debug("Turning heating on")
        HeaterObject.switch(ON)
        write_event("APIHEST", "on", "HEATSTA", "on", False)
    elif status is False:
        logger.debug("Turning heating off")
        HeaterObject.switch(OFF)
        write_event("APIHEST", "off", "HEATSTA", "off", False)
    else:
        abort(400)  # Send bad request error

    return jsonify({"response": "OK"})  # Send OK response in JSON format


# Blind state change API call
@app.route("/cabinapi/setblind", methods=["POST"])
def setblind():
    logger.debug("Blind state change request received")
    logger.debug(f"Request body: {request.json}")

    # Test for correct JSON request
    if not request.json or ("blind" and "position" not in request.json):
        abort(400)  # Send bad request error

    # Get blind and position from request
    selected_blind = request.json["blind"]
    position = request.json["position"]

    # Check if position is in range and blind name exists, then set blind
    if 10 <= position <= 20:
        if selected_blind in blind_objects:
            set_blind(selected_blind, position)
            write_event("APIBDST", f"{selected_blind}, {position}", "BLNDSTA", f"{selected_blind}, {position}", False)
        elif selected_blind == "all":
            set_all_blinds(position)
            write_event("APIBDST", f"all, {position}", "BLNDSTA", f"all, {position}", False)
        else:
            abort(400)  # Send bad request error
    else:
        abort(400)  # Send bad request error

    return jsonify({"response": "OK"})  # Send OK response in JSON format


# Heating interface update API call
@app.route("/cabinapi/getheating", methods=["GET"])
def getheating():
    logger.debug("Heating interface update request received")

    # Get global variables
    global heating_mode, desired_temp

    # Obtain current temperature
    logger.debug("Getting temperature")
    current_temperature = tempsensor.get_temperature()

    # Obtain current heating state
    heating_state = HeaterObject.get_state()

    # Return response
    return jsonify({"response": "OK",
                    "current_temp": current_temperature,
                    "desired_temp": desired_temp,
                    "mode": heating_mode,
                    "status": heating_state})


# Blind interface update API call
@app.route("/cabinapi/getblinds", methods=["GET"])
def getblinds():
    logger.debug("Blind interface update request received")

    # Compile blind positions
    blind_positions = {}
    for current_blind in blind_objects:
        blind_positions[current_blind] = blind_objects[current_blind].state

    return jsonify({"response": "OK",
                    "positions": blind_positions})


# Check if the Dark Sky API key file exists and get the key
def get_api_key(file_name):
    global use_darksky_api
    try:
        file = open(file_name, "r")  # Open file where key is stored
        key = file.read()  # Read key from file
        file.close()  # Close file
        use_darksky_api = True
        return key
    except FileNotFoundError:  # Prevent a crash if the file is missing
        use_darksky_api = False  # Stops functions using the API from running
        logger.warning("Dark Sky API key file is missing; functions that use this API will not run.")
        logger.warning(f"To use Dark Sky API functions, create a file called \"{file_name}\"")
        logger.warning(f"in \"{os.getcwd()}\", insert the API key into the file, and run this program again.")
        # os.getcwd() gets the current file path of where the program is stored


# Check if the event log database exists
def check_database_exists(file_name):
    global use_database
    if os.path.isfile("./" + file_name):
        use_database = True
    else:  # If the file is missing
        use_database = False  # Stops functions using the database from running
        logger.warning("Event log database file is missing; functions that use this database will not run.")


def validate_database_structure(file_name):
    global use_database
    if use_database:
        try:
            conn = connect_database(DATABASE_FILE_NAME)
            queries = ["SELECT EventID, Timestamp, TriggerCode, TriggerDetails, ResponseCode, ResponseDetails, Automated FROM EventLog",
                       "SELECT TriggerCode, Name, Description, Details FROM Triggers",
                       "SELECT ResponseCode, Name, Description, Details FROM Responses"]
            with conn:
                for query in queries:
                    cur = conn.cursor()
                    cur.execute(query)
            use_database = True
        except Error:
            use_database = False  # Stops functions using the database from running
            logger.warning("Event log database file is not properly set up; functions that use this database will not run.")

def main():
    global API_KEY

    # Get Dark Aky API key
    API_KEY = get_api_key(DARKSKY_API_KEY_FILE_NAME)

    # Check if event log database exists
    check_database_exists(DATABASE_FILE_NAME)

    # Check if event log database structure is valid
    validate_database_structure(DATABASE_FILE_NAME)

    # Start presence detection
    logger.debug(energenie.setup(emulation))
    
    # Set heating and devices to off
    HeaterObject.switch(OFF)
    DevicesObject.switch(OFF)

    # Start each blind object
    for blind in blind_objects:
        blind_objects[blind].start()

    # Close all blinds
    logger.debug("Closing all blinds")
    set_all_blinds(CLOSED)

    # Run this unless interrupted by KeyboardInterrupt
    try:
        # Start API thread
        app_thread.start()

        logger.info("Setup complete")
        while True:  # Run forever
            main_loop()
    except KeyboardInterrupt:  # Exit program cleanly when CTRL + C is pressed down
        logger.info("Shutting down")

        # Shutdown presence detection
        logger.debug(energenie.finish())

        # Shutdown each blind object
        for blind in blind_objects:
            blind_objects[blind].stop()

        # Shutdown logging system
        logging.shutdown()


if __name__ == "__main__":
    main()
