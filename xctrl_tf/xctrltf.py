import XTouch as XTouch
import tf as tf
import time
#import keyboard
import logging
import _thread

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)
global x2tf
METER_HISTORY_LENGTH = 10
FADER_TIMEOUT = 2

#callbacks
def updateTFFader (index,value):
    db = x2tf.xtouch.fader_value_to_db(value)
    if index <= 7:
        chan = x2tf.xtouchChToTFCh(index)
        x2tf.fader_values[chan] = db * 100
        x2tf.t.sendFaderValue(chan,db)
    if index == 8: #main fader
        if x2tf.main_fader_rev == False:
            x2tf.t.sendMainFaderValue(db)
        else:
            x2tf.t.sendMainFXFaderValue(db,x2tf.fx_select)
        x2tf.main_fader_value = db * 100
    
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

def onFaderIconRcv (chan, icon):
    x2tf.updateFaderIcon(chan,icon)

def onChannelMute(chan, value):
    value =  not value
    x2tf.updateChannelMute(chan,value)

def onChannelSolo (chan,value):
    x2tf.updateChannelSolo(chan,value)

def onChannelMasterMute (chan,value):
    value = not value
    x2tf.updateChannelMasterMute(chan,value)

def buttonPress (button):
    logger.info('%s (%d) %s' % (button.name, button.index, 'pressed' if button.pressed else 'released'))
    if 'Mute' not in button.name and 'Group' not in button.name and 'Send' not in button.name and 'Sel' not in button.name and 'Global' not in button.name and 'Flip' not in button.name and 'Drop' not in button.name and 'Solo' not in button.name:
        button.SetLED(button.pressed)
    if button.name == 'BankRight' and button.pressed:
        if x2tf.fader_offset <=23:
            x2tf.fader_offset += 8
            if x2tf.fader_offset > 24:
                x2tf.fader_offset = 24
        x2tf.updateDisplay()
    if button.name == 'BankLeft' and button.pressed:
        if x2tf.fader_offset >= 8:
            x2tf.fader_offset -= 8
        else:
            x2tf.fader_offset = 0
            x2tf.updateDisplay()
    if button.name == 'ChannelRight' and button.pressed:
        if x2tf.fader_offset <= 23:
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
        button.SetLED(x2tf.ch_mutes[x2tf.xtouchChToTFCh(ch)])
        x2tf.updateDisplay()
    if 'Solo' in button.name and button.pressed==True:
        ch = int(button.name.replace('Ch','').replace('Solo','')) - 1
        x2tf.ch_solos[x2tf.xtouchChToTFCh(ch)] = not x2tf.ch_solos[x2tf.xtouchChToTFCh(ch)]
        val = x2tf.ch_solos[x2tf.xtouchChToTFCh(ch)]
        x2tf.t.sendChannelSolo(x2tf.xtouchChToTFCh(ch),val)
        val = x2tf.getSoloOn(ch)        
        if val == 0 or val == 1:
            button.SetLED(bool(val))
        else:
            button.BlinkLED()
        x2tf.updateDisplay()
    if 'Drop' in button.name and button.pressed==True:
        x2tf.mute_first_bank = not x2tf.mute_first_bank
        button.SetLED(x2tf.mute_first_bank)
        if x2tf.mute_first_bank:
            val = True
        else:
            val = False
        for i in range(8):
            x2tf.ch_mutes[i] = val
            x2tf.t.sendChannelMute(i,x2tf.ch_mutes[i])
        x2tf.updateDisplay()
    if 'Sel' in button.name and button.pressed == True:
        ch = int(button.name.replace('Ch','').replace('Sel','')) - 1
        x2tf.fader_select_en[x2tf.xtouchChToTFCh(ch)] = not x2tf.fader_select_en[x2tf.xtouchChToTFCh(ch)] 
        button.SetLED(x2tf.fader_select_en[x2tf.xtouchChToTFCh(ch)])
        x2tf.chan_encoder_group_adjustment = 0 #reset adjustment
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
       button.SetLED(x2tf.global_fx_on)
       x2tf.updateDisplay()
    if button.name == 'Flip' and button.pressed == True:
       x2tf.main_fader_rev = not x2tf.main_fader_rev
       button.SetLED(x2tf.main_fader_rev)
       x2tf.updateDisplay()
    if 'Touch' in button.name:
        if button.name != "MainTouch":
            ch = int(button.name.replace('Ch','').replace('Touch','')) - 1
            x2tf.xtouch_fader_in_use[ch] = button.pressed
        else:
            ch = 8
            x2tf.xtouch_fader_in_use[ch] = button.pressed
        x2tf.xtouch_fader_in_use_timeout[ch] = time.time()

    

def onGlobalMuteRcv (value):
    x2tf.global_fx_on = not value
    x2tf.pendingDisplayUpdate = True

def onFXSendValueRcv(fx_select, chan, value):
    if fx_select == 0:
        x2tf.fx1_sends[chan] = tf.fader_value_to_db(value)
    if fx_select == 1:
        x2tf.fx2_sends[chan] = tf.fader_value_to_db(value)
    x2tf.pendingDisplayUpdate = True

def onFXSendEnValueRcv (fx_select, chan, on):
    logger.debug ('fx_select ' +str(fx_select) + 'chan '+str(chan)+' on '+str(on))
    v = False
    if on == 1:
        v = True
    if fx_select == 0:
        x2tf.fx1_send_en[chan] = v
    if fx_select == 1:
        x2tf.fx2_send_en[chan] = v
    x2tf.pendingDisplayUpdate = True

last_encoder_time = time.time()

def encoderChange(index, direction):
    global last_encoder_time
    logger.debug ("encoder change "+str(index)+" "+str(direction))
    if (index < 8):
        chan = x2tf.xtouchChToTFCh(index)
        fx = x2tf.chooseFX(chan)
        if fx == 0:
            send_value =  x2tf.fx1_sends[chan] + (2.5 * direction)
            if send_value >= 0:
                send_value = 0
            x2tf.t.sendFXSend(0,chan,send_value)
            x2tf.fx1_sends[chan] = send_value
        else:
            send_value =  x2tf.fx2_sends[chan] + (2.5 * direction)
            if send_value >= 0:
                send_value = 0
            x2tf.t.sendFXSend(1,chan,send_value)
            x2tf.fx2_sends[chan] = send_value
        x2tf.pendingDisplayUpdate = True
        #update encoder
        if fx == 0:
            x2tf.xtouch.channels[index].SetEncoderValue(x2tf.dbToEncoder(x2tf.fx1_sends[chan]))
        else:
            x2tf.xtouch.channels[index].SetEncoderValue(x2tf.dbToEncoder(x2tf.fx2_sends[chan]))
    if index == 44: #big knob
        chlist=x2tf.getChSelected()
        stop = False
        for ch in chlist:
            #implement limits 5db to -50db
            if (x2tf.fader_values[ch] >= (5 * 100)) and direction > 0:
                stop = True
            if (x2tf.fader_values[ch] < (-50 * 100)) and direction < 0:
                stop = True
        if stop == False:
            x2tf.chan_encoder_group_adjustment = x2tf.chan_encoder_group_adjustment  + (300 * direction) #3db
            if (time.time() - last_encoder_time) > 0.5:
                for ch in chlist:
                    x2tf.fader_values[ch] = x2tf.fader_values[ch] + x2tf.chan_encoder_group_adjustment
                    x2tf.updateFader(ch,x2tf.fader_values[ch])
                    x2tf.t.sendFaderValue(ch,x2tf.fader_values[ch],noConvert=True)
                x2tf.chan_encoder_group_adjustment = 0
                last_encoder_time = time.time()
            


class xctrltf:

    def __init__(self, xtouch_ip='192.168.10.80', tf_ip='192.168.10.10'):
        self.map_by_color_en = False
        self.fx_select = 0
        self.pendingDisplayUpdate = True
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
        self.t.onFaderIconRcv = onFaderIconRcv
        self.t.onFXSendEnValueRcv = onFXSendEnValueRcv
        self.t.onChannelMasterMute = onChannelMasterMute
        self.t.onChannelSolo = onChannelSolo
        self.fader_select_en = [False] * 40
        self.mute_first_bank = False
        self.fx1_sends = [-120] * 40
        self.fx2_sends =  [-120] * 40
        self.fx1_send_en = [False] * 40
        self.fx2_send_en = [False] * 40
        self.chan_encoder_group_adjustment = 0
        self.fader_offset = 0
        self.global_fx_on = True
        self.fader_names = ['ch'] * 40
        self.fader_colors = [7]*40
        self.fader_icons = ['none']*40
        self.fader_values = [1000]*40
        self.main_fader_value = 0
        self.main_fader_rev = False
        self.main_rev_fader_value = [0] * 2
        self.xtouch_fader_in_use = [False]*9
        self.xtouch_fader_in_use_timeout = [time.time()]*9
        self.xtouchext_fader_in_use = [False]*8
        self.xtouchext_fader_in_use_timeout = [time.time()]*8
        self.xtouch_last_meter_update = time.time()
        self.ch_solos = [False]*40
        self.ch_mutes = [False]*40
        self.ch_master_mutes = [False] * 40
        self.ch_custom_map = list(range(40)) 
        self.color_order = [2,5,7,6,3,1,4,0]
        self.icon_order = ['DynamicMic','A.Guitar','Keyboard','E.Guitar','E.Bass','Drumkit','Choir','Piano','Audience','PC','SpeechMic','WirelessMic']
        self.running = True
        _thread.start_new_thread(self.periodicDisplayRefresh, ())
        if self.t.mix != 0:
            self.xtouch.GetButton('Aux').SetLED(True)
        else:
            self.xtouch.GetButton('Aux').SetLED(False)

    def syncTF2XTouch (self):
        for i in range(32):
            self.t.getFaderValue(i)
            time.sleep(0.01)
            self.t.getFaderName(i)
            time.sleep(0.01)
            self.t.getFaderColor(i)
            time.sleep(0.01)
            self.t.getFaderIcon(i)
            time.sleep(0.01)
            self.t.getChannelOn(i)
            time.sleep(0.02)
            self.t.getFX1Send(i)
            time.sleep(0.01)
            self.t.getFX2Send(i)
            time.sleep(0.01)
            self.t.getChannelSoloOn(i)
        self.t.getMainFaderValue()
        self.t.getMainFXFaderValue(0)
        self.t.getMainFXFaderValue(1)

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
        #icons = ['DynamicMic','A.Guitar','Keyboard','E.Guitar','E.Bass','Drumkit','Choir','Piano','Audience','PC','SpeechMic','WirelessMic']
        logger.info ("fader icons")
        logger.info (str(self.fader_icons))
        new_map = []
        '''
        for c in self.color_order:
            for index, fc in enumerate(self.fader_colors):
                if fc == c:
                    new_map.append(index)
        '''
        new_map = [0,1,2,3,4,5,6,7, 8,9,10,11,12,13,14,15, 24,25,26,27,28,29,30,31, 16,17,18,19,20,21,22,23] #custom grouping
        self.ch_custom_map = new_map

    def xtouchChToTFCh (self, fader_index):
        if self.map_by_color_en == False:
            return self.fader_offset + fader_index
        else:
            return self.ch_custom_map[self.fader_offset + fader_index]
    
    def tfChToXtouchCh (self, chan_index):
        if self.map_by_color_en == False:
            return chan_index - self.fader_offset
        else:
            return self.ch_custom_map.index(chan_index) - self.fader_offset
    
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

    def chooseFX (self, chan):
        logger.debug (str(self.fx1_send_en) + '   '+ str(self.fx2_send_en))
        if (self.fx2_send_en[chan] and self.fx1_send_en[chan]) or (not self.fx2_send_en[chan] and not self.fx1_send_en[chan]):
            if self.fx_select == 0:
                fx = 0
            else:
                fx = 1
        elif self.fx2_send_en[chan]:
            fx = 1
        else:
            fx = 0
        return fx
    
    def getChannelOn (self, xtouchIndex):
        chan = self.xtouchChToTFCh(xtouchIndex)
        master = self.ch_master_mutes[chan]
        aux = self.ch_mutes[chan]
        if master or aux:
            return False
        return True

    def getSoloOn (self, xtouchIndex):
        chan = self.xtouchChToTFCh(xtouchIndex)
        master = self.ch_master_mutes[chan]
        aux = self.ch_solos[chan]
        if (not master) and aux:
            return 1
        if aux:
            return 2
        return 0

    def updateDisplay(self):
        if self.t._active == False:
            for i in range(8):
                self.xtouch.SendScribble(i, 'Discon', 'nected', 1, False)
        else:
            if self.main_fader_rev == False:
                maindb = tf.fader_value_to_db(self.main_fader_value)
                mainv = self.xtouch.fader_db_to_value(maindb)
                if self.xtouch_fader_in_use[8] == False and (time.time() - self.xtouch_fader_in_use_timeout[8] > FADER_TIMEOUT): 
                    self.xtouch.SendSlider(8,mainv)
            else:
                maindb = tf.fader_value_to_db(self.main_rev_fader_value[self.fx_select])
                mainv = XTouch.fader_db_to_value(maindb)
                if self.xtouch_fader_in_use[8] == False and (time.time() - self.xtouch_fader_in_use_timeout[8] > FADER_TIMEOUT): 
                    self.xtouch.SendSlider(8,mainv)
            for i in range(8):
                chan = self.xtouchChToTFCh(i)
                db = tf.fader_value_to_db(self.fader_values[chan])
                v = self.xtouch.fader_db_to_value(db)
                if self.xtouch_fader_in_use[i] == False and (time.time() - self.xtouch_fader_in_use_timeout[i] > FADER_TIMEOUT):
                    self.xtouch.SendSlider(i,v)
                name = self.fader_names[chan][0:6]
                channelno = str(chan+1)[0:6]
                if self.fader_names[chan][6:] != "":
                    channelno = (self.fader_names[chan][6:]+' '+str(chan+1))[0:6]
                color = self.fader_colors[chan]
                logger.debug ("index "+str(i)+' name:'+name+' chan '+channelno+' color '+str(color))
                self.xtouch.SendScribble(i, name, channelno, color, False)
                #choose fx index
                fx = self.chooseFX(chan)
                #update encoder
                if fx == 0:
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
            self.xtouch.GetButton('Ch1Rec').SetLED(self.getChannelOn(0))
            self.xtouch.GetButton('Ch2Rec').SetLED(self.getChannelOn(1))
            self.xtouch.GetButton('Ch3Rec').SetLED(self.getChannelOn(2))
            self.xtouch.GetButton('Ch4Rec').SetLED(self.getChannelOn(3))
            self.xtouch.GetButton('Ch5Rec').SetLED(self.getChannelOn(4))
            self.xtouch.GetButton('Ch6Rec').SetLED(self.getChannelOn(5))
            self.xtouch.GetButton('Ch7Rec').SetLED(self.getChannelOn(6))
            self.xtouch.GetButton('Ch8Rec').SetLED(self.getChannelOn(7))
            for i in range(8):
                name = "Ch" + str(i+1)+"Solo"
                val = self.getSoloOn(i)
                button = self.xtouch.GetButton(name)
                if val == 0 or val == 1:
                    button.SetLED(bool(val))
                else:
                    button.BlinkLED()
            self.xtouch.GetButton('PlugIn').SetLED(True) #encoder fx 
            self.xtouch.GetButton('Global').SetLED(self.global_fx_on) #encoder fx 
            self.xtouch.GetButton('Flip').SetLED(self.main_fader_rev) #main fader rev fx 

    def periodicDisplayRefresh(self):
        while self.running:
            k = 0
            if self.connected:      
                fader_in_use = any(self.xtouch_fader_in_use) or any(self.xtouchext_fader_in_use)
                while (self.t.isQueueEmpty() == False):
                    time.sleep(0.1)
                for i in range(8):
                    if self.xtouch_fader_in_use[i] == False and (time.time() - self.xtouch_fader_in_use_timeout[i] > FADER_TIMEOUT):
                        self.t.getFaderValue(self.xtouchChToTFCh(i))
                    self.t.getChannelOn(self.xtouchChToTFCh(i))
                    if k % 6 == 0:
                        self.t.getFaderName(self.xtouchChToTFCh(i))
                        self.t.getFaderColor(self.xtouchChToTFCh(i))     
                        self.t.getChannelSoloOn(self.xtouchChToTFCh(i))               
                    self.t.getFX1Send(self.xtouchChToTFCh(i))
                    self.t.getFX2Send(self.xtouchChToTFCh(i))
                    while (self.t.isQueueEmpty() == False):
                        time.sleep(0.1)
                if self.xtouch_fader_in_use[8] == False and (time.time() - self.xtouch_fader_in_use_timeout[8] > FADER_TIMEOUT): 
                    self.t.getMainFaderValue()
                    self.t.getMainFXFaderValue(0)
                    self.t.getMainFXFaderValue(1)
                if self.pendingDisplayUpdate: 
                    self.updateDisplay() 
                    self.pendingDisplayUpdate = False
                if k%6==0:
                    k = 0
                k = k + 1
                time.sleep(0.5)
                if fader_in_use:
                    time.sleep(1)

    def wait_for_connect (self):
        while (self.xtouch._active == False) or (self.t._active == False):
            time.sleep(1)
            if self.xtouch._active == False:
                print ("waiting to connect to xtouch...")
            if self.t._active == False:
                print ("waiting to connect to tf...")
        self.connected = True
    
    def updateChannelMute(self,chan, value):
        self.ch_mutes[chan] = value
        self.pendingDisplayUpdate = True

    def updateChannelSolo(self,chan,value):
        self.ch_solos[chan] = value
        self.pendingDisplayUpdate = True

    def updateChannelMasterMute(self, chan, value):
        self.ch_master_mutes[chan] = value
        self.pendingDisplayUpdate = True

    def updateFader (self, chan,value):
        self.fader_values[chan] = value
        index = self.tfChToXtouchCh(chan)
        db = tf.fader_value_to_db(value)
        v = self.xtouch.fader_db_to_value(db)
        if index >= 0 and index < 8:
            if self.xtouch_fader_in_use[index] == False and (time.time() - self.xtouch_fader_in_use_timeout[index] > FADER_TIMEOUT):
                self.xtouch.SendSlider(index,v)

    def updateMainFader (self, value):
        self.main_fader_value = value
        if self.main_fader_rev == False:
            index = 8
            db = tf.fader_value_to_db(value)
            v = self.xtouch.fader_db_to_value(db)
            if self.xtouch_fader_in_use[index] == False and (time.time() - self.xtouch_fader_in_use_timeout[index] > FADER_TIMEOUT):
                self.xtouch.SendSlider(index,v)

    def updateMainFXFader (self, fx, value):
        self.main_rev_fader_value[fx] = value
        index = 8
        if self.main_fader_rev and self.fx_select == fx:
            db = tf.fader_value_to_db(value)
            v = self.xtouch.fader_db_to_value(db)
            if self.xtouch_fader_in_use[index] == False and (time.time() - self.xtouch_fader_in_use_timeout[index] > FADER_TIMEOUT):
                self.xtouch.SendSlider(index,v)

    def updateFaderName(self,chan,value):
        if value == "" or value is None:
            value = str(chan)
        self.fader_names[chan] = value
    
    def updateFaderIcon (self, chan, icon):
        if icon == "" or icon is None:
            icon = "none"
        self.fader_icons[chan] = icon

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
        if color == 0: #we dont want any "off"
            color = 7
        self.fader_colors[chan] = color

    def update_meter (self, location, value):
        logger.debug ("meter loc = "+str(location)+" value = "+str(value))
        self.xtouch.SetMeterLevelPeak(location, value)

    def update_ch_meters (self, values):
        meter_values = [self.xtouch.db_to_meter_value(num) for num in values]
        display_meters = []
        if time.time()-self.xtouch_last_meter_update > 0.3:
            self.xtouch_last_meter_update = time.time()
            for i in range(8):
                display_meters.append(meter_values[self.xtouchChToTFCh(i)])
                self.update_meter (i,display_meters[i])

    def update_main_meter(self, values):
        self.update_meter (9,values[9]) #aux9

    def stop_running (self):
        self.xtouch.running = False
        self.t.running = False
        self.running = False
    

running = True

print ("Press q to quit")
'''
def on_key_event(event):
    global running
    if event.name == 'q' and event.event_type == keyboard.KEY_DOWN:
        print(" 'q' pressed. Exiting loop.")
        running = False

keyboard.on_press(on_key_event)
'''
x2tf = xctrltf()
firstSync = True
synced = False
while running:
    time.sleep(1)
    if x2tf.t._active:
        if firstSync:
            x2tf.t.enableSoloBus()
            time.sleep(5)
            x2tf.syncTF2XTouch()
            time.sleep(5)
            x2tf.syncTF2XTouch()
            time.sleep(5)
            x2tf.syncTF2XTouch()
            firstSync = False
            x2tf.pendingDisplayUpdate = True
            synced = True
            logger.info ("Finished syncing")
        else:
            if synced == False:
                x2tf.t.enableSoloBus()
                time.sleep(2)
                x2tf.syncTF2XTouch()
                logger.info ("syncing after reconnect")
                x2tf.pendingDisplayUpdate = True
                synced = True
    else:
        synced=False
x2tf.stop_running()


