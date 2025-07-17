import XTouch as XTouch
import tf as tf
import time
import keyboard
import logging

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)
global x2tf
METER_HISTORY_LENGTH = 10


#callbacks
def updateTFFader (index,value):
    db = XTouch.fader_value_to_db(value)
    cmd = 'set MIXER:Current/InCh/Fader/Level '+str(index)+' 0 '+tf.fader_db_to_value(db) 
    x2tf.t.send_command(cmd)

    
def chMeterRcv (values):
    x2tf.update_ch_meters(values)

def mixMeterRcv (values):
    x2tf.update_main_meter(values)

def buttonPress (button):
    logger.info('%s (%d) %s' % (button.name, button.index, 'pressed' if button.pressed else 'released'))
    button.SetLED(button.pressed)
    if button.name == 'BankRight' and button.pressed:
        x2tf.fader_offset += 8
    if button.name == 'BankLeft' and button.pressed:
        if x2tf.fader_offset >= 8:
            x2tf.fader_offset -= 8
    if button.name == 'ChannelRight' and button.pressed:
        x2tf.fader_offset += 1
    if button.name == 'ChannelLeft' and button.pressed:
        if x2tf.fader_offset >= 1:
            x2tf.fader_offset -= 1

class xctrltf:

    def __init__(self, xtouch_ip='192.168.10.9'):
        self.t = tf.tf_rcp()
        self.xtouch = XTouch.XTouch(xtouch_ip)
        self.wait_for_connect()
        self.xtouch.setOnButtonChange(buttonPress)
        self.xtouch.GetButton('Flip').setOnChange(XTouch.PrintFlip)
        self.xtouch.GetButton('Flip').setOnDown(XTouch.FlipPress)
        self.xtouch.GetButton('Flip').setOnUp(XTouch.FlipRelease)
        self.xtouch.setOnSliderChange(updateTFFader)
        self.xtouch.SendSlider(0,8192)
        self.xtouch.SendScribble(0, "hi", "there", 6, False)
        self.t.setOnChMeterRcv(chMeterRcv)
        #self.t.setOnMixMeterRcv(mixMeterRcv)
        self.fader_offset = 0


    def wait_for_connect (self):
        while (self.xtouch._active == False) and (self.t._active == False):
            time.sleep(1)
            print ("waiting to connect...")

    def update_meter (self, location, value):
        logger.debug ("meter loc = "+str(location)+" value = "+str(value))
        self.xtouch.SetMeterLevelPeak(location, value)

    def update_ch_meters (self, values):
        meter_values = [XTouch.db_to_meter_value(num) for num in values]
        if self.fader_offset < 24: 
            display_meters = meter_values[self.fader_offset : self.fader_offset  + 8]
            for i in range(8):
                self.update_meter (i,display_meters[i])

    def update_main_meter(self, values):
        self.update_meter (9,values[9]) #aux9

    def stop_running (self):
        self.xtouch.running = False
        self.t.running = False
    



x2tf = xctrltf()
input("Press enter to quit...")


