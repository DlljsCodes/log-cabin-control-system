### Blind Control - Servo Module

### Version: Control ###
### Ver 1 9/11/19: First version

import time

### Raspberry Pi specific modules
RPi_module_import_fail = False
try:
   import RPi.GPIO as GPIO
except ImportError:
   RPi_module_import_fail = True

#----------------- Set general control constants  -------------------
ON = True
OFF = False
REPEAT_ENERGENIE = 2
   
#----------------- Set GPIO Constants  ------------------------------
# Energenie Constants - Note BCM numbering
DATA3 = 27  # Pin 13
DATA2 = 23  # Pin 16
DATA1 = 22  # Pin 15
DATA0 = 17  # Pin 11
FSK_SELECT = 24 # Pin 18
MODULATOR = 25  # Pin 22
# Codes for switching on and off the sockets
#        all     1       2       3       4
SKT_ON  = ['1011', '1111', '1110', '1101', '1100']
SKT_OFF = ['0011', '0111', '0110', '0101', '0100']

#----------------- Global variables for module ---------------------
simulation_mode = False


def setup(simulation=False):
    global simulation_mode
    if simulation:
        log_message = log_message ='Running in simulation mode. '
        simulation_mode=True
    else:
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(FSK_SELECT, GPIO.OUT)
        GPIO.setup(MODULATOR, GPIO.OUT)
        GPIO.setup(DATA0, GPIO.OUT)
        GPIO.setup(DATA1, GPIO.OUT)
        GPIO.setup(DATA2, GPIO.OUT)
        GPIO.setup(DATA3, GPIO.OUT)
        # Set FSK on Energenie
        GPIO.output(FSK_SELECT, GPIO.LOW)
        # Turn off modulator
        GPIO.output(MODULATOR, GPIO.LOW)
    
    if simulation_mode:
        log_message = 'Energenie module setup complete, running in simulation mode'
    else:
        log_message = 'Energenie module setup complete'
    return log_message


def finish():
    global simulation_mode
    if not simulation_mode:
        GPIO.cleanup()

    log_message = 'Cleaned up GPIO. '
    return log_message


def switchEnergenie(socket,state,logger,repeat=1):
    global simulation_mode
    if simulation_mode:
        logger.info("Switch Energenie (SIMULATION): %s with repeat %d" % (state[socket],repeat))
    # Set data pins
    else:
        logger.info("Switch Energenie: %s with repeat %d" % (state[socket],repeat))
        GPIO.output(DATA0, int(state[socket][3]))
        GPIO.output(DATA1, int(state[socket][2]))
        GPIO.output(DATA2, int(state[socket][1]))
        GPIO.output(DATA3, int(state[socket][0]))
        for x in range(1,repeat):
            # Allow pin changes to settle
            time.sleep(1)
            # Turn on modulator
            GPIO.output(MODULATOR, GPIO.HIGH)
            # Wait
            time.sleep(1)
            # Turn off modulator
            GPIO.output(MODULATOR, GPIO.LOW)


class device():
    def __init__(self,socket_number,logger):
        self.socket_number = socket_number
        self.logger = logger
        self.state = False
        
    def get_state(self):
        return self.state

    def switch(self,state):
        if state == ON:
            switchEnergenie(self.socket_number, SKT_ON,self.logger,REPEAT_ENERGENIE)
            self.state = True
        else:
            switchEnergenie(self.socket_number, SKT_OFF,self.logger,REPEAT_ENERGENIE)
            self.state = False


class GPIOInputDevice:
    def __init__(self, pin_number, presence_callback):
        self.pin_number = pin_number
        self.presence_callback = presence_callback
        self.state = False
        # Setup the Cabin PIR Pin
        GPIO.setup(self.pin_number, GPIO.IN)
        # Setup Interrupt for Cabin PIR Sensor
        GPIO.add_event_detect(self.pin_number, GPIO.RISING, self.presence_callback)

    def get_state(self):
        self.state = GPIO.input(self.pin_number)
        return self.state
