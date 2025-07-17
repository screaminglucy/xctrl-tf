import XTouch as XTouch
import tf as tf
import time
import keyboard
import logging
import _thread

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)
global x2tf
METER_HISTORY_LENGTH = 10

#callbacks
def updateTFFader (index,value):
    db = XTouch.fader_value_to_db(value)
    if index <= 7:
        chan = x2tf.xtouchChToTFCh(index)
        x2tf.t.sendFaderValue(chan,db)
    
def chMeterRcv (values):
    x2tf.update_ch_meters(values)

def mixMeterRcv (values):
    x2tf.update_main_meter(values)

def onFaderValueRcv (chan, value):
    x2tf.updateFader(chan,value)

def onFaderNameRcv (chan, name):
    x2tf.updateFaderName(chan,name)

def onFaderColorRcv (chan, color):
    x2tf.updateFaderColor(chan,color)

def onChannelMute(chan, value):
    value =  not value
    x2tf.updateChannelMute(chan,value)

def buttonPress (button):
    logger.info('%s (%d) %s' % (button.name, button.index, 'pressed' if button.pressed else 'released'))
    if 'Mute' not in button.name:
        button.SetLED(button.pressed)
    if button.name == 'BankRight' and button.pressed:
        if x2tf.fader_offset <=31:
            x2tf.fader_offset += 8
            if x2tf.fader_offset > 32:
                x2tf.fader_offset = 32
        x2tf.updateDisplay()
    if button.name == 'BankLeft' and button.pressed:
        if x2tf.fader_offset >= 8:
            x2tf.fader_offset -= 8
            x2tf.updateDisplay()
    if button.name == 'ChannelRight' and button.pressed:
        if x2tf.fader_offset <= 31:
            x2tf.fader_offset += 1
            x2tf.updateDisplay()
    if button.name == 'ChannelLeft' and button.pressed:
        if x2tf.fader_offset >= 1:
            x2tf.fader_offset -= 1
            x2tf.updateDisplay()
    if button.name == 'Scrub' and button.pressed==False:
        x2tf.syncTF2XTouch()
        x2tf.updateDisplay()
    if 'Mute' in button.name and button.pressed==True:
        ch = int(button.name.replace('Ch','').replace('Mute','')) - 1
        x2tf.ch_mutes[x2tf.xtouchChToTFCh(ch)] = not x2tf.ch_mutes[x2tf.xtouchChToTFCh(ch)]
        x2tf.t.sendChannelMute(x2tf.xtouchChToTFCh(ch),x2tf.ch_mutes[x2tf.xtouchChToTFCh(ch)])
        x2tf.updateDisplay()

    

class xctrltf:

    def __init__(self, xtouch_ip='192.168.10.9'):
        self.t = tf.tf_rcp()
        self.xtouch = XTouch.XTouch(xtouch_ip)
        self.connected = False
        self.wait_for_connect()
        self.xtouch.setOnButtonChange(buttonPress)
        self.xtouch.GetButton('Flip').setOnChange(XTouch.PrintFlip)
        self.xtouch.GetButton('Flip').setOnDown(XTouch.FlipPress)
        self.xtouch.GetButton('Flip').setOnUp(XTouch.FlipRelease)
        self.xtouch.setOnSliderChange(updateTFFader)
        self.t.setOnChMeterRcv(chMeterRcv)
        self.t.onFaderValueRcv = onFaderValueRcv
        self.t.onFaderColorRcv = onFaderColorRcv
        self.t.onFaderNameRcv = onFaderNameRcv
        self.t.onChannelMute = onChannelMute
        self.fader_offset = 0
        self.fader_names = ['ch'] * 40
        self.fader_colors = [7]*40
        self.fader_values = [1000]*40
        self.ch_mutes = [False]*40
        self.ch_map_by_color = list(range(40)) 
        self.map_by_color = False
        self.running = True
        _thread.start_new_thread(self.periodicDisplayRefresh, ())
    
    def syncTF2XTouch (self):
        for i in range(40):
            self.t.getFaderValue(i)
            time.sleep(0.01)
            self.t.getFaderName(i)
            time.sleep(0.01)
            self.t.getFaderColor(i)
            time.sleep(0.01)
            self.t.getChannelOn(i)
            time.sleep(0.01)
        self.createColorMap()

    def createColorMap(self):
        pass

    def xtouchChToTFCh (self, fader_index):
        if self.map_by_color == False:
            return self.fader_offset + fader_index
    
    def tfChToXtouchCh (self, chan_index):
        if self.map_by_color == False:
            return chan_index - self.fader_offset
    
    def updateDisplay(self):
        for i in range(8):
            chan = self.xtouchChToTFCh(i)
            db = tf.fader_value_to_db(self.fader_values[chan])
            v = XTouch.fader_db_to_value(db)
            self.xtouch.SendSlider(i,v)
            self.xtouch.SendScribble(i, self.fader_names[chan], str(chan+1), self.fader_colors[chan], False)
        self.xtouch.GetButton('Ch1Mute').SetLED(self.ch_mutes[self.xtouchChToTFCh(0)])
        self.xtouch.GetButton('Ch2Mute').SetLED(self.ch_mutes[self.xtouchChToTFCh(1)])
        self.xtouch.GetButton('Ch3Mute').SetLED(self.ch_mutes[self.xtouchChToTFCh(2)])
        self.xtouch.GetButton('Ch4Mute').SetLED(self.ch_mutes[self.xtouchChToTFCh(3)])
        self.xtouch.GetButton('Ch5Mute').SetLED(self.ch_mutes[self.xtouchChToTFCh(4)])
        self.xtouch.GetButton('Ch6Mute').SetLED(self.ch_mutes[self.xtouchChToTFCh(5)])
        self.xtouch.GetButton('Ch7Mute').SetLED(self.ch_mutes[self.xtouchChToTFCh(6)])
        self.xtouch.GetButton('Ch8Mute').SetLED(self.ch_mutes[self.xtouchChToTFCh(7)])

    def periodicDisplayRefresh(self):
        while self.running:
            if self.connected:
                for i in range(8):
                    self.t.getFaderValue(self.xtouchChToTFCh(i))
                    time.sleep(0.01)
                    self.t.getFaderName(self.xtouchChToTFCh(i))
                    time.sleep(0.01)
                    self.t.getFaderColor(self.xtouchChToTFCh(i))
                    time.sleep(0.01)
                    self.t.getChannelOn(self.xtouchChToTFCh(i))
                    time.sleep(0.01)
                self.updateDisplay()
                time.sleep(1)

    def wait_for_connect (self):
        while (self.xtouch._active == False) or (self.t._active == False):
            time.sleep(1)
            print ("waiting to connect...")
        self.connected = True
    
    def updateChannelMute(self,chan, value):
        self.ch_mutes[chan] = value

    def updateFader (self, chan,value):
        self.fader_values[chan] = value
        index = self.tfChToXtouchCh(chan)
        db = tf.fader_value_to_db(value)
        v = XTouch.fader_db_to_value(db)
        if index >= 0 and index < 8:
            self.xtouch.SendSlider(index,v)

    def updateFaderName(self,chan,value):
        if value == "" or value is None:
            value = str(chan)
        self.fader_names[chan] = value
    
    def updateFaderColor(self,chan,value):
        index = self.tfChToXtouchCh(chan)
        try:
            color = XTouch.XTouch.Channel.Color[value].value
        except:
            logger.error (value + " has no color match")
            if value == "Purple":
                color = 5 #pink
                logger.warning ("using pink!")
            elif value == "SkyBlue":
                color = 6 #cyan
                logger.warning ("using cyan!")
            else:
                color = 7
                logger.warning ("using white!")
        self.fader_colors[chan] = color

    def update_meter (self, location, value):
        logger.debug ("meter loc = "+str(location)+" value = "+str(value))
        self.xtouch.SetMeterLevelPeak(location, value)

    def update_ch_meters (self, values):
        meter_values = [XTouch.db_to_meter_value(num) for num in values]
        display_meters = []
        for i in range(8):
            display_meters.append(meter_values[self.xtouchChToTFCh(i)])
            self.update_meter (i,display_meters[i])

    def update_main_meter(self, values):
        self.update_meter (9,values[9]) #aux9

    def stop_running (self):
        self.xtouch.running = False
        self.t.running = False
        self.running = False
    



x2tf = xctrltf()
time.sleep(5)
x2tf.syncTF2XTouch()
time.sleep(2)
x2tf.syncTF2XTouch()
time.sleep(2)
x2tf.syncTF2XTouch()
input("Press enter to quit...")
x2tf.stop_running()


