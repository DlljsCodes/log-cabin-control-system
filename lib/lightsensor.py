# Compatibility module for Adafruit TSL2591 High Dynamic Range Digital Light Sensor
# By Lexi Stevens

# Import libraries
try:
    import board
    import busio
    import adafruit_tsl2591
    module_fail = False
except ModuleNotFoundError:
    module_fail = True
except NotImplementedError:
    module_fail = True

class LightSensor:
    def __init__(self, logger, gain="med", integration_time=100):
        self.emulation_mode = module_fail
        self.logger = logger
        self.logger.debug("Setting up light sensor object")
        if self.emulation_mode:
            self.emulation_values = {
                "lux": 50,
                "visible": 50,
                "infrared": 50,
                "full_spectrum": 50,
                "raw_luminosity": 50}
            self.logger.debug("Running in emulation mode")
        else:
            self.i2c = busio.I2C(board.SCL, board.SDA)
            self.sensor = adafruit_tsl2591.TSL2591(self.i2c)
        self.set_gain(gain)
        self.set_integration_time(integration_time)

    def get_measurement(self, measurement):
        measurements = ["lux", "visible", "infrared", "full_spectrum", "raw_luminosity"]
        if measurement in measurements:
            if self.emulation_mode:
                return self.emulation_values[measurement]
            else:
                if measurement == "lux":
                    return self.sensor.lux
                elif measurement == "visible":
                    return self.sensor.visible
                elif measurement == "infrared":
                    return self.sensor.infrared
                elif measurement == "full_spectrum":
                    return self.sensor.full_spectrum
                elif measurement == "raw_luminosity":
                    return self.sensor.raw_luminosity
        else:
            raise ValueError("Specified measurement value not valid.")

    def set_gain(self, gain):
        if self.emulation_mode:
            gains = {
                "low": 1,
                "med": 25,
                "high": 428,
                "max": 9876}
        else:
            gains = {
                "low": adafruit_tsl2591.GAIN_LOW,
                "med": adafruit_tsl2591.GAIN_MED,
                "high": adafruit_tsl2591.GAIN_HIGH,
                "max": adafruit_tsl2591.GAIN_MAX}
        if gain in gains:
            self.logger.debug(f"Setiing light sensor gain value to {gain}")
            if self.emulation_mode:
                self.emu_gain = gains[gain]
            else:
                self.sensor.gain = gains[gain]
        else:
            raise ValueError("Specified gain value not valid.")

    def set_integration_time(self, integration_time):
        if self.emulation_mode:
            integration_times = {
                100: 100,
                200: 200,
                300: 300,
                400: 400,
                500: 500,
                600: 600}
        else:
            integration_times = {
                100: adafruit_tsl2591.INTEGRATIONTIME_100MS,
                200: adafruit_tsl2591.INTEGRATIONTIME_200MS,
                300: adafruit_tsl2591.INTEGRATIONTIME_300MS,
                400: adafruit_tsl2591.INTEGRATIONTIME_400MS,
                500: adafruit_tsl2591.INTEGRATIONTIME_500MS,
                600: adafruit_tsl2591.INTEGRATIONTIME_600MS}
        if integration_time in integration_times:
            self.logger.debug(f"Setiing light sensor integration time value to {integration_time}ms")
            if self.emulation_mode:
                self.emu_integration_time = integration_times[integration_time]
            else:
                self.sensor.integration_time = integration_times[integration_time]
        else:
            raise ValueError("Specified integration time value not valid.")
