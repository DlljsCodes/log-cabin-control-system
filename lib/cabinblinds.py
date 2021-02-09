### Blind Control - Servo Module

### Change Log
### Ver 1 11/7/19: Implemented as a module
### Ver 2 9/11/19: Added simulation mode for Lexi development. Included hardware specific modules and removed from main program

import threading
import time
from datetime import datetime
from datetime import timedelta

### Raspberry Pi specific modules
RPi_module_import_fail = False
try:
   import board
except ImportError:
   RPi_module_import_fail = True
except NotImplementedError:
   RPi_module_import_fail = True

try:
   import busio
except ImportError:
   RPi_module_import_fail = True
   
try:
   import adafruit_pca9685
except ImportError:
   RPi_module_import_fail = True

### Setup Constants ###
START_STATE = 10
WAIT_TIME = 15 # Seconds

# Each blind will have it's own object running as a thread. This allows to check for a certain time after being activated and set incative.
# Reason is that sometimes the sail winch servos won't quite stop and buzz so want to set duty cycle to 0 after certain amount of time
class blindservo(threading.Thread):
    def __init__(self, blindname, pcachannel,logger,simulation=False):
        self.stoprequest = threading.Event()
        self.pcachannel = pcachannel
        self.blindname = blindname
        self.pcachannel = pcachannel
        self.simulation=simulation
        self.state = START_STATE
        self.duty_cycle=3276
        self.logger = logger
        ### Setup PCA9685  ###
        # From https://learn.adafruit.com/adafruit-16-channel-pwm-servo-hat-for-raspberry-pi/using-the-python-library
        if not simulation: # Code below dependant on RPi hardware specific modules
            self.i2c = busio.I2C(board.SCL, board.SDA)
            self.pca = adafruit_pca9685.PCA9685(self.i2c)
            self.pca.frequency = 50

        # Check if we have modules imported and not running in simulation
        if not simulation and RPi_module_import_fail:
            self.logger.warning('Blind modules failed to load and not running in simulation mode')
        
        # This is where the servo is actually controlled. If in simulation mode, we create a dummy servo object. If not, we assign our servo to the right PCA channel object
        if simulation:
            class simulation_servo():
                duty_cycle = 0
            self.servo = simulation_servo()
        else:        
            self.servo = self.pca.channels[pcachannel] # Key code here: Assign our servo object to a PCA channel object
        self.time_set = datetime.now()
        self.active = False
        threading.Thread.__init__(self)
        self.logger.debug('Initialised servo object %s with channel %d' %(self.blindname, self.pcachannel))
    
    def stop(self):
        self.logger.debug('Stopping the servo object %s with channel %d' %(self.blindname, self.pcachannel))
        self.servo.duty_cycle = 0
        self.stoprequest.set()    

    def run(self):
        self.logger.debug('Running the servo object %s with channel %d' %(self.blindname, self.pcachannel))

        # Run the thread until stoprequest is set
        while not self.stoprequest.isSet():
            #self.logger.debug('%s servo running and my state is %d and my duty_cycle is %d' %(self.blindname,self.state, self.duty_cycle))
            # If last time state changed was over WANT_TIME seconds ago, set duty cycle to 0 to stop the servo completely
            if self.active and (datetime.now() > self.time_set + timedelta(seconds=WAIT_TIME)):
                self.logger.debug('Setting to 0')
                self.servo.duty_cycle = 0
                self.active = False
                self.logger.debug('Setting servo object %s with channel %d to inactive' %(self.blindname, self.pcachannel))
            # Sleep so not taking too much CPU
            time.sleep(1)

    def set_state(self, state):
        self.state = state
        self.duty_cycle = int((self.state * 0xffff)/200)
        self.servo.duty_cycle = self.duty_cycle
        self.active = True
        self.time_set = datetime.now()
        self.logger.debug('Setting servo object %s with channel %d to state %d with duty cycle %d' %(self.blindname, self.pcachannel, self.state, self.duty_cycle))

