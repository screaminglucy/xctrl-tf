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
    if index == 8: #main fader
        if x2tf.main_fader_rev == False:
            x2tf.t.sendMainFaderValue(db)
        else:
            x2tf.t.sendMainFXFaderValue(db,x2tf.fx_select)
    
def chMeterRcv (values):
    x2tf.update_ch_meters(values)

def mixMeterRcv (values):
    x2tf.update_main_meter(values)

def onFaderValueRcv (chan, value):
    x2tf.updateFader(chan,value)

def onFaderNameRcv (chan, name):
    x2tf.updateFaderName(chan,name)

def onMainFaderValueRcv(val):
    x2tf.updateMainFader(val)

def onMainFXFaderValueRcv(fx_select, value):
    x2tf.updateMainFXFader(fx_select,value)

def onFaderColorRcv (chan, color):
    x2tf.updateFaderColor(chan,color)

def onChannelMute(chan, value):
    value =  not value
    x2tf.updateChannelMute(chan,value)

def buttonPress (button):
    logger.info('%s (%d) %s' % (button.name, button.index, 'pressed' if button.pressed else 'released'))
    if 'Mute' not in button.name and 'Group' not in button.name and 'Send' not in button.name and 'Sel' not in button.name and 'Global' not in button.name and 'Flip' not in button.name:
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
    if 'Sel' in button.name and button.pressed == True:
        ch = int(button.name.replace('Ch','').replace('Sel','')) - 1
        x2tf.fader_select_en[x2tf.xtouchChToTFCh(ch)] = not x2tf.fader_select_en[x2tf.xtouchChToTFCh(ch)] 
        button.SetLED(x2tf.fader_select_en[x2tf.xtouchChToTFCh(ch)])
    if button.name == 'Cancel' and button.pressed==False:
        x2tf.fader_select_en = [False] * 40
        x2tf.updateDisplay()
    if button.name == 'Group' and button.pressed==False:
        x2tf.fader_offset = 0
        logger.debug ("recalculating color groups")
        x2tf.map_by_color_en = not x2tf.map_by_color_en
        button.SetLED(x2tf.map_by_color_en)
        x2tf.createColorMap()
        x2tf.updateDisplay()
    if button.name == 'Send' and button.pressed==False:
        if x2tf.fx_select == 0:
            x2tf.fx_select = 1
        else:
            x2tf.fx_select = 0
        button.SetLED(x2tf.fx_select == 1)
        x2tf.updateDisplay()
    if button.name == 'Global' and button.pressed == True:
       x2tf.global_fx_on = not x2tf.global_fx_on
       x2tf.t.sendGlobalFxMute (not x2tf.global_fx_on)
       x2tf.updateDisplay()
    if button.name == 'Flip' and button.pressed == True:
       x2tf.main_fader_rev = not x2tf.main_fader_rev
       x2tf.updateDisplay()
    

def onGlobalMuteRcv (value):
    x2tf.global_fx_on = not value

def onFXSendValueRcv(fx_select, chan, value):
    if fx_select == 0:
        x2tf.fx1_sends[chan] = tf.fader_value_to_db(value)
    if fx_select == 1:
        x2tf.fx2_sends[chan] = tf.fader_value_to_db(value)

def encoderChange(index, direction):
    logger.info ("encoder change "+str(index)+" "+str(direction))
    if (index < 8):
        chan = x2tf.xtouchChToTFCh(index)
        if x2tf.fx_select == 0:
            x2tf.fx1_sends[chan] = x2tf.fx1_sends[chan] + (2.5 * direction)
            x2tf.t.sendFXSend(0,chan,x2tf.fx1_sends[chan])
        else:
            x2tf.fx2_sends[chan] = x2tf.fx2_sends[chan] + (2.5 * direction)
            x2tf.t.sendFXSend(1,chan,x2tf.fx2_sends[chan])
    if index == 44: #big knob
        chlist=x2tf.getChSelected()
        for ch in chlist:
            x2tf.fader_values[ch] = x2tf.fader_values[ch] + (200 * direction) #2db
            x2tf.updateFader(ch,x2tf.fader_values[ch])
            x2tf.t.sendFaderValue(ch,x2tf.fader_values[ch],noConvert=True)



class xctrltf:

    def __init__(self, xtouch_ip='192.168.10.9', tf_ip='192.168.10.5'):
        self.map_by_color_en = False
        self.fx_select = 0
        self.t = tf.tf_rcp(tf_ip)
        self.xtouch = XTouch.XTouch(xtouch_ip)
        self.connected = False
        self.wait_for_connect()
        self.xtouch.setOnButtonChange(buttonPress)
        self.xtouch.setOnEncoderChange(encoderChange)
        self.xtouch.setOnSliderChange(updateTFFader)
        self.t.setOnChMeterRcv(chMeterRcv)
        self.t.onFaderValueRcv = onFaderValueRcv
        self.t.onMainFaderValueRcv = onMainFaderValueRcv
        self.t.onFaderColorRcv = onFaderColorRcv
        self.t.onFaderNameRcv = onFaderNameRcv
        self.t.onFXSendValueRcv = onFXSendValueRcv
        self.t.onGlobalMuteRcv = onGlobalMuteRcv
        self.t.onMainFXFaderValueRcv = onMainFXFaderValueRcv
        self.t.onChannelMute = onChannelMute
        self.fader_select_en = [False] * 40
        self.fx1_sends = [-120] * 40
        self.fx2_sends =  [-120] * 40
        self.fader_offset = 0
        self.global_fx_on = True
        self.fader_names = ['ch'] * 40
        self.fader_colors = [7]*40
        self.fader_values = [1000]*40
        self.main_fader_value = 0
        self.main_fader_rev = False
        self.main_rev_fader_value = [0] * 2
        self.ch_mutes = [False]*40
        self.ch_map_by_color = list(range(40)) 
        self.color_order = [2,5,3,6,7,1,4,0]
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
            self.t.getFX1Send(i)
            time.sleep(0.01)
            self.t.getFX2Send(i)
        self.t.getMainFaderValue()

    def getChSelected (self):
        true_indices = [i for i, val in enumerate(self.fader_select_en) if val]
        return true_indices

    def createColorMap(self):
        # colors are 0-7 
        #    Off = 0
        #    Red = 1
        #    Green = 2
        #    Yellow = 3
        #    Blue = 4
        #    Pink = 5 (purple)
        #    Cyan = 6 (skyblue)
        #    White = 7 (orange)
        new_map = []
        for c in self.color_order:
            for index, fc in enumerate(self.fader_colors):
                if fc == c:
                    new_map.append(index)
        self.ch_map_by_color = new_map

    def xtouchChToTFCh (self, fader_index):
        if self.map_by_color_en == False:
            return self.fader_offset + fader_index
        else:
            return self.ch_map_by_color[self.fader_offset + fader_index]
    
    def tfChToXtouchCh (self, chan_index):
        if self.map_by_color_en == False:
            return chan_index - self.fader_offset
        else:
            return self.ch_map_by_color.index(chan_index) - self.fader_offset
    
    def dbToEncoder (self, db):
        if db >= 0:
            return 6
        db = 30 + db
        if (db < 0):
            return -6
        v = (db / 2.5) - 6
        if v < -6:
            v = -6
        return v

    def updateDisplay(self):
        if self.main_fader_rev == False:
            maindb = tf.fader_value_to_db(self.main_fader_value)
            mainv = XTouch.fader_db_to_value(maindb)
            self.xtouch.SendSlider(8,mainv)
        else:
            maindb = tf.fader_value_to_db(self.main_rev_fader_value[self.fx_select])
            mainv = XTouch.fader_db_to_value(maindb)
            self.xtouch.SendSlider(8,mainv)
        for i in range(8):
            chan = self.xtouchChToTFCh(i)
            db = tf.fader_value_to_db(self.fader_values[chan])
            v = XTouch.fader_db_to_value(db)
            self.xtouch.SendSlider(i,v)
            self.xtouch.SendScribble(i, self.fader_names[chan], str(chan+1), self.fader_colors[chan], False)
            if self.fx_select == 0:
                self.xtouch.channels[i].SetEncoderValue(self.dbToEncoder(self.fx1_sends[chan]))
            else:
                self.xtouch.channels[i].SetEncoderValue(self.dbToEncoder(self.fx2_sends[chan]))
        self.xtouch.GetButton('Ch1Mute').SetLED(self.ch_mutes[self.xtouchChToTFCh(0)])
        self.xtouch.GetButton('Ch2Mute').SetLED(self.ch_mutes[self.xtouchChToTFCh(1)])
        self.xtouch.GetButton('Ch3Mute').SetLED(self.ch_mutes[self.xtouchChToTFCh(2)])
        self.xtouch.GetButton('Ch4Mute').SetLED(self.ch_mutes[self.xtouchChToTFCh(3)])
        self.xtouch.GetButton('Ch5Mute').SetLED(self.ch_mutes[self.xtouchChToTFCh(4)])
        self.xtouch.GetButton('Ch6Mute').SetLED(self.ch_mutes[self.xtouchChToTFCh(5)])
        self.xtouch.GetButton('Ch7Mute').SetLED(self.ch_mutes[self.xtouchChToTFCh(6)])
        self.xtouch.GetButton('Ch8Mute').SetLED(self.ch_mutes[self.xtouchChToTFCh(7)])
        self.xtouch.GetButton('Ch1Sel').SetLED(self.fader_select_en[self.xtouchChToTFCh(0)])
        self.xtouch.GetButton('Ch2Sel').SetLED(self.fader_select_en[self.xtouchChToTFCh(1)])
        self.xtouch.GetButton('Ch3Sel').SetLED(self.fader_select_en[self.xtouchChToTFCh(2)])
        self.xtouch.GetButton('Ch4Sel').SetLED(self.fader_select_en[self.xtouchChToTFCh(3)])
        self.xtouch.GetButton('Ch5Sel').SetLED(self.fader_select_en[self.xtouchChToTFCh(4)])
        self.xtouch.GetButton('Ch6Sel').SetLED(self.fader_select_en[self.xtouchChToTFCh(5)])
        self.xtouch.GetButton('Ch7Sel').SetLED(self.fader_select_en[self.xtouchChToTFCh(6)])
        self.xtouch.GetButton('Ch8Sel').SetLED(self.fader_select_en[self.xtouchChToTFCh(7)])
        if self.t.mix != 0:
            self.xtouch.GetButton('Aux').SetLED(True)
        else:
            self.xtouch.GetButton('Aux').SetLED(False)
        self.xtouch.GetButton('PlugIn').SetLED(True) #encoder fx 
        self.xtouch.GetButton('Global').SetLED(self.global_fx_on) #encoder fx 
        self.xtouch.GetButton('Flip').SetLED(self.main_fader_rev) #main fader rev fx 

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
                    self.t.getFX1Send(self.xtouchChToTFCh(i))
                    time.sleep(0.01)
                    self.t.getFX2Send(self.xtouchChToTFCh(i))
                    time.sleep(0.01)
                    self.t.getMainFaderValue()
                    time.sleep(0.01)
                    self.t.getMainFXFaderValue(0)
                    time.sleep(0.01)
                    self.t.getMainFXFaderValue(1)
                    time.sleep(0.100)
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

    def updateMainFader (self, value):
        self.main_fader_value = value
        if self.main_fader_rev == False:
            index = 8
            db = tf.fader_value_to_db(value)
            v = XTouch.fader_db_to_value(db)
            self.xtouch.SendSlider(index,v)

    def updateMainFXFader (self, fx, value):
        self.main_rev_fader_value[fx] = value
        index = 8
        if self.main_fader_rev and self.fx_select == fx:
            db = tf.fader_value_to_db(value)
            v = XTouch.fader_db_to_value(db)
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
            if value == "Purple":
                color = 5 #pink
                logger.warning (value + " no color match using pink!")
            elif value == "SkyBlue":
                color = 6 #cyan
                logger.warning (value + " no color match using cyan!")
            else:
                color = 7
                logger.warning (value + " no color match using white!")
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


