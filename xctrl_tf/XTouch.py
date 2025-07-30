from enum import Enum
from datetime import datetime
import threading
import _thread
import socket
from time import sleep
import sys
import mido
import logging
import math
import time
import queue

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# XCTRL network mode
# or USB mackie control

timeout = 60

class XTouch:

    def __init__(self, use_extender=False):
        self.ip = None
        self.usb_name = "X-Touch"
        self.usb_extender_name = "X-Touch-Ext"
        self.extender = use_extender
        self.usb_enabled = False
        self.outbound_q = queue.Queue()
        self.channels = []
        for i in range(9):
            self.channels.append(self.Channel(self, i))
        self.buttons = self.Buttons(self)
        self.onButtonChange = None
        self.onSliderChange = None
        self.onEncoderChange = None
        self._active = False
        self.lastMsgTime = None
        self.connect()

    def fader_value_to_db (self, value):
        if self.usb_enabled:
            if (value == -8192):
                db = -120
            else:
                value = int((value + 8192)*2)
                db = 20*math.log10(value / 24575) *3.5
                if value > 24575:
                    db = (value - 24575) / 800
            db = int (db)
            logger.debug ("todb: fader value = "+str(value)+ " db value = "+str(db))
            return db
        else:
            if (value == 0):
                db = -120
            else:
                db = 20*math.log10(value / 24575) *3.5
                if value > 24575:
                    db = (value - 24575) / 800
            db = int (db)
            logger.debug ("todb: fader value = "+str(value)+ " db value = "+str(db))
            return db

    def fader_db_to_value (self, db):
        if self.usb_enabled:
            value = math.pow(10,((db/3.5)/20))*24575
            if (db > 0):
                value = (db * 800)+24575
            if (db < -100):
                value = 0
            if value < 0:
                value = 0
            value = int (value)
            value = ( value / 2 ) - 8192
            value = int (value)
            logger.debug ("tovalue: fader value = "+str(value)+ ", db value = "+str(db))
            return value
        else:
            value = math.pow(10,((db/3.5)/20))*24575
            if (db > 0):
                value = (db * 800)+24575
            if (db < -100):
                value = 0
            if value < 0:
                value = 0
            value = int (value)
            logger.debug ("tovalue: fader value = "+str(value)+ " db value = "+str(db))
            return value

    def db_to_meter_value(self, db):
        #fudged for now
        db = db + 16
        if (db < 0):
            db = db * 3
        if (db >= -10):
            return 8
        if (db > -15 and db < -10):
            return 7
        if (db > -20 and db <= -18):
            return 6
        if (db > -15 and db <= -18):
            return 5
        if (db > -25 and db <= -15):
            return 4
        if (db > -35 and db <= -25):
            return 3
        if (db > -40 and db <= -35):
            return 2
        if (db > -55 and db <= -40):
            return 1
        return 0

    @property
    def active(self):
        return self._active

    @active.setter
    def active(self, val: bool):
        self._active = val
        self.SendAll()

    def setOnButtonChange(self, callback):
        self.onButtonChange = callback

    def setOnSliderChange(self, callback):
        self.onSliderChange = callback

    def setOnEncoderChange(self, callback):
        self.onEncoderChange = callback

    def connect_usb(self):
        logger.info ("Connect usb")
        in_port_name = self.usb_name
        out_port_name = self.usb_name
        try:
            ins = mido.get_input_names()
            outs = mido.get_output_names()
            if self.extender == False:
                for i in ins:
                    if self.usb_name in i and self.usb_extender_name not in i:
                        in_port_name = i
                for o in outs:
                    if self.usb_name in o and self.usb_extender_name not in o:
                        out_port_name = o
            else:
                for i in ins:
                    if self.usb_extender_name in i:
                        in_port_name = i
                for o in outs:
                    if self.usb_extender_name in o:
                        out_port_name = o
            self.output_port = mido.open_output(out_port_name)
            self.input_port = mido.open_input(in_port_name)
            self.running = True
            self.usb_enabled = True
            _thread.start_new_thread(self.getUSBMsg, ())
            _thread.start_new_thread(self.processOutgoingUSBPackets, ())
            self._active = True
            logger.info("Midi connection opened")
            return True
        except OSError as e:
            logger.error(f"Error opening MIDI port: {e}")
            return False

    
    def connect(self):
        if self.connect_usb() == False:
            if self.extender == False:
                self.connect_xctrl()

    def connect_xctrl(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        host = ''
        port = 10111
        self.sock.bind((host, port))
        self.running = True
        _thread.start_new_thread(self.getMsg, ())
        _thread.start_new_thread(self.processOutgoingPackets, ())
        logger.info("Connection opened")
        self.SendKeepAlive()

    def getUSBMsg(self):
        while self.running:
            if self.input_port is not None:
                msg = self.input_port.receive(block=True)
                self._active = True
                self.HandleMsg(msg)
                self.lastMsgTime = time.time() 
   
    def processOutgoingUSBPackets (self):
        logger.info ("xtouch processOutgoingUSBPackets() thread started")
        while self.running:
            try :
                msg = self.outbound_q.get(block=False)
                logger.debug ("sending "+str(msg))
                self.output_port.send(msg)
                self.counter += 1
                if self.counter % 8 == 0:
                    time.sleep(0.001) #let other things run!
                    self.counter = 1
            except :
                time.sleep(0.001)
        self.output_port.close()
        self.input_port.close()    

    def getMsg(self):
        while self.running:
            data, addr = self.sock.recvfrom(10111)
            if self.ip == None or self.ip != addr[0]:
                self.ip = addr[0]
                logger.info(f"Accepted connection from {addr}")
                self._active = True
            self.HandleMsg(data)
            self.lastMsgTime = time.time() 
    
    def processOutgoingPackets (self):
        logger.info ("xtouch processOutgoingPackets() thread started")
        while self.running:
            try :
                msg = self.outbound_q.get(block=False)
                logger.debug ("sending "+str(msg))
                self.sock.sendto(bytearray(msg), (self.ip, 10111))
                time.sleep(0.001)
            except :
                time.sleep(0.001)

    def clearOutgoingPackets(self):
        empty = self.outbound_q.empty()
        while empty == False:
            msg = self.outbound_q.get(block=True)
            empty = self.outbound_q.empty()

    def sendRawMsg(self, msg):
        self.outbound_q.put(msg)

    def sendMidiControl(self, index, value):
        self.sendRawMsg(bytearray([0xF0, 0xD0, index, value, 0xF7]))

    def SendAll(self):
        for c in self.channels:
            c.SendAll()
        for b in self.buttons:
            self.SendButton(b)

    def SendButton(self, index, value):
        if self.usb_enabled:
            msg = mido.Message ('note_on', note=index, velocity = value )
            self.sendRawMsg(msg)
        else:
            self.sendRawMsg(bytearray([0xF0, 0x90, 0x00 + index, value, 0xF7]))

    def SendSlider(self, index, value):
        if self.usb_enabled:
            msg = mido.Message('pitchwheel', channel=index, pitch=value)
            self.sendRawMsg(msg)
        else:
            self.sendRawMsg(bytearray([0xF0, 0xE0 + index] + list(value.to_bytes(2, sys.byteorder)) +  [0xF7]))

    def SendEncoder(self, index, values):
        if self.usb_enabled:
            value = values - 1
            if value < 0:
                value = 0
            value = 0x20 | value
            msg = mido.Message('control_change', control=48+index, value=value)
            logger.debug (str(msg))
            self.sendRawMsg(msg)
        else:
            left = ''.join(['1' if v else '0' for v in values][:7])
            right = ''.join(['1' if v else '0' for v in values][7:])
            logger.debug('left '+ str(left))
            logger.debug('right '+ str(right))
            logger.debug ('values '+str(values))
            self.sendRawMsg(bytearray([0xF0, 0xB0, 48 + index, int(left, 2), 0xF7]))
            self.sendRawMsg(bytearray([0xF0, 0xB0, 56 + index, int(right, 2), 0xF7]))

    def SendScribble(self, index, topText, bottomText, color, bottomInverted):
        if self.usb_enabled:
            self.channels[index].scribbleColor = color 
            deviceByte = 0x15
            if self.extender == False:
                deviceByte = 0x14
            colors = []
            for i in range(8):
                colors.append(int(self.channels[i].scribbleColor))
            logger.debug ("send scribble " +topText +" " + bottomText)
            msg = mido.Message('sysex', data=([0x00, 0x00, 0x66, deviceByte, 0x12, 0x00 + (index*7)] + list(bytearray(topText.ljust(7, '\0'), 'utf-8')) ))
            self.sendRawMsg(msg)
            msg = mido.Message('sysex', data=([0x00, 0x00, 0x66, deviceByte, 0x12, 0x38 + (index*7)] + list(bytearray(bottomText.ljust(7, '\0'), 'utf-8')) ))
            self.sendRawMsg(msg)
            msg = mido.Message('sysex', data=([0x00, 0x00, 0x66, deviceByte, 0x72] + list(colors)))
            self.sendRawMsg(msg)
        else:
            logger.debug ("send scribble " +topText +" " + bottomText)
            self.sendRawMsg(bytearray([0xF0, 0x00, 0x00, 0x66, 0x58, 0x20 + index, (0x00 if not bottomInverted else 0x40) + color]
                + list(bytearray(topText.ljust(7, '\0'), 'utf-8')) + list(bytearray(bottomText.ljust(7, '\0'), 'utf-8')) + [0xF7]))

    def SendMeter(self, index, level):
        if self.usb_enabled:
            msg = mido.Message('aftertouch',value=(index<<4)|level)
            self.sendRawMsg(msg)
        else:
            self.meter_levels[index] = level
            logger.debug (self.meter_levels)
            self.SendMeters()
            #self.sendRawMsg(bytearray([0xF0, 0xD0, 0x00, index + level, 0xF7]))

    def SendMeters(self):
        if self.usb_enabled:
            for i in range (8):
                self.SendMeter(i,self.channels[i].GetMeterLevel())
        else:
            self.sendRawMsg(bytearray([0xF0, 0xD0, 0x00, 0 + self.channels[0].GetMeterLevel(), 16 + self.channels[1].GetMeterLevel(), 32 + self.channels[2].GetMeterLevel() , 48 + self.channels[3].GetMeterLevel(), 64 + self.channels[4].GetMeterLevel(), \
            80 + self.channels[5].GetMeterLevel(), 96 + self.channels[6].GetMeterLevel(), 112 + self.channels[7].GetMeterLevel(),0xF7]))
    
    def SetMeterLevel(self, channel, level):
        self.channels[channel].SetMeterLevel(level)

    def SetMeterLevelPeak(self, channel, level):
        self.channels[channel].SetMeterLevelPeak(level)
    
    def SendKeepAlive(self):
        if self.running:
            self.sendRawMsg([0xF0, 0x00, 0x00, 0x66, 0x14, 0x00, 0xF7])
            threading.Timer(6, self.SendKeepAlive).start()
            if self.lastMsgTime is not None:
                if (time.time() - self.lastMsgTime) > timeout:
                    logger.info(f"Dropped connection from {self.ip}")
                    self.ip = None
                    self._active = False

    def HandleMsg(self, data):
        if self.usb_enabled:
            self.lastMsg = datetime.now()
            msg_type = data.type
            logger.debug ("message type: "+str(msg_type))
            if msg_type == 'note_on':
                note = data.note
                velocity = data.velocity
                logger.debug ("note "+str(note) + " velocity "+str(velocity))
            if msg_type == 'control_change':
                control = data.control
                value = data.value
                logger.debug ("control " + str(control) + " value "+ str(value))
            if msg_type == 'pitchwheel':
                channel = data.channel
                value = data.pitch
            data = data.bin()
            logger.debug ("Received: "+str(data))
            if msg_type == 'note_on':
                self.buttons.buttons[note].pressed = int(velocity) == 127
                if self.onButtonChange:
                    self.onButtonChange(self.buttons.buttons[note])
            elif msg_type == 'control_change':
                if control >= 16 and control <= 23:
                    direction = 1
                    if value >= 65:
                        direction = -1
                    control = control - 16
                    if self.onEncoderChange:
                        self.onEncoderChange(int(control), direction)
                    logger.info('Encoder: (' + str(control) + ', ' + str(direction) + ')')
            elif msg_type == 'pitchwheel':
                logger.debug('Fader: (' + str(channel) + ', ' + str(value) + ')')
                self.SendSlider(channel, value) #send value back to confirm and stop glitchy faders
                if self.onSliderChange:
                    self.onSliderChange(channel, int(value))
        else:
            self.lastMsg = datetime.now()
            #Keep alive message
            if data == bytearray([0xF0, 0x00, 0x20, 0x32, 0x58, 0x54, 0x00, 0xF7]):
                return
            #Confirmation message
            if data == bytearray([0xF0, 0x00, 0x00, 0x66, 0x58, 0x01, 0x30, 0x31, 0x35, 0x36, 0x34, 0x30, 0x37, 0x44, 0x37, 0x37, 0x39, 0xF7]):
                return

            #print('Length: ', len(data))
            if data[0] == 0x90:
                self.buttons.buttons[int(data[1])].pressed = int(data[2]) == 127
                if self.onButtonChange:
                    self.onButtonChange(self.buttons.buttons[int(data[1])])
            elif data[0] >= 0xE0 and data[0] <= 0xE8:
                channel = int(data[0] - 0xE0)
                value = int(data[2] << 8 | data[1])
                logger.debug('Fader: (' + str(channel) + ', ' + str(value) + ')')
                self.SendSlider(channel, value) #send value back right away to confirm and stop glitchy faders
                if self.onSliderChange:
                    self.onSliderChange(channel, value)
            elif data[0] == 0xB0:
                if self.onEncoderChange:
                    self.onEncoderChange(int(data[1] - 0x10), int(0x40 - data[2]) if data[2] > 0x40 else data[2])
                logger.info('Encoder: (' + str(int(data[1] - 0x10)) + ', ' + str(int(-(data[2] - 0x40) if data[2] > 0x40 else data[2])) + ')')
            elif data[0] == 0xF0:
                logger.debug('System: ' + str( [hex(d) for d in data]))
            else:
                logger.info('Unknown: ' + str( [hex(d) for d in data]))

    def GetButton(self, name: str):
        return self.buttons.GetButton(name)


    class Channel:
        class Color(Enum):
            Off = 0
            Red = 1
            Green = 2
            Yellow = 3
            Blue = 4
            Pink = 5
            Cyan = 6
            White = 7

        def __init__(self, parent, index):
            self.xtouch = parent
            self.index = index

            # Scribble variables
            self.scribbleTopText = ''
            self.scribbleBottomText = ''
            self.scribbleColor = self.Color.White.value
            self.bottomInverted = False

            # Slider value
            self.slider = 0

            # Encoder values
            self.encoderValue = 0
            self.encoderFromCenter = True
            self.encoderBetween = False

            # Meter values
            self.meterDecay = True
            self.meterLevel = 0
            self.meter_history = [0]

        def SetAll(self):
            self.SendSlider()
            self.SendEncoder()
            self.SendScribble()

        #
        # Slider
        #
        def SetSlider(self, value):
            self.sliderValue = value
            self.SendSlider()

        def SendSlider(self):
            self.xtouch.SendSlider(self.index, self.sliderValue)

        #
        # Encoder Lights
        #
        def SetEncoderValue(self, value):
            # This value goes from -6 to 6 (including floats)
            self.encoderValue = value
            self.SendEncoder()

        def SetEncoderFromCenter(self, fromCenter: bool):
            self.encoderFromCenter = fromCenter
            self.SendEncoder()

        def SetEncoderBetween(self, between: bool):
            self.encoderBetween = between
            self.SendEncoder()

        def SendEncoder(self):
            if self.xtouch.usb_enabled:
                enc = self.encoderValue
                logger.debug (' encoderValue ' + str(self.encoderValue))
                enc = enc + 6 #make positive
                self.xtouch.SendEncoder(self.index, int(enc))
                logger.debug ('encoder:'+str(self.index)+'  value = '+ str(enc))
            else:
                enc = self.encoderValue
                logger.debug (' encoderValue ' + str(self.encoderValue))
                if self.encoderFromCenter:
                    values = [enc>=0, enc >= -1, enc >= -2, enc >= -3, enc >= -4, enc >= -5, enc >= -6, enc >= 6, enc >= 5, enc >= 4, enc >= 3, enc >= 2, enc >= 1]
                elif self.encoderBetween:
                    values = [enc <= -5.25, enc >= -5.75 and enc <= -4.25, enc >= -4.75 and enc <= -3.25, enc >= -3.75 and enc <= -2.25, enc >= -2.75 and enc <= -1.25, enc >= -1.75 and enc <= -0.25, enc >= -0.75 and enc <= 0.75, enc >= 0.25 and enc <= 1.75, enc >= 1.25 and enc <= 2.75, enc >= 2.25 and enc <= 3.75, enc >= 3.25 and enc <= 4.75, enc >= 4.25 and enc <= 5.75, enc >= 5.25]
                else:
                    values =  [enc < -5.5, enc >= -5.5 and enc < -4.5, enc >= -4.5 and enc < -3.5, enc >= -3.5 and enc < -2.5, enc >= -2.5 and enc < -1.5, enc >= -1.5 and enc < -0.5, enc >= -0.5 and enc < 0.5, enc >= 0.5 and enc < 1.5, enc >= 1.5 and enc < 2.5, enc >= 2.5 and enc < 3.5, enc >= 3.5 and enc < 4.5, enc >= 4.5 and enc < 5.5, enc >= 5.5]
                self.xtouch.SendEncoder(self.index, values)
                logger.debug ('values = '+ str(values))
        #
        # Scribble Strip
        #
        def SetScribble(self, topText: str, bottomText: str, color: Color, bottomInverted: bool):
            self.scribbleTopText = topText
            self.scribbleBottomText = bottomText
            self.scribbleColor = color
            self.bottomInverted = bottomInverted
            self.SendScribble()

        def SetScribbleText(self, topText: str, bottomText: str):
            self.scribbleTopText = topText
            self.scribbleBottomText = bottomText
            self.SendScribble()

        def SetScribbleTopText(self, topText: str):
            self.scribbleTopText = topText
            self.SendScribble()

        def SetScribbleBottomText(self, bottomText: str):
            self.scribbleBottomText = bottomText
            self.SendScribble()

        def SetScribbleColor(self, color: Color):
            self.scribbleColor = color
            self.SendScribble()

        def SetScribbleInverted(self, bottomInverted: bool):
            self.bottomInverted = bottomInverted
            self.SendScribble()

        def SendScribble(self):
            self.xtouch.SendScribble(self.index, self.scribbleTopText, self.scribbleBottomText, self.scribbleColor, self.bottomInverted)


        #
        # Meters
        #
        def SetMeterLevel(self, level: int):
            if level < 0:
                level = 0
            if level > 8:
                level = 8
            self.meterLevel = level
            self.xtouch.SendMeters()

        def SetMeterLevelPeak(self, level: int):
            self.meter_history.append(level)
            self.SetMeterLevel(max(self.meter_history))
            self.meterLevel = max(self.meter_history)
            if len (self.meter_history) > 2:
                self.meter_history = self.meter_history[1:]
            self.xtouch.SendMeters()

        def SetMeterDecay(self, decay: bool):
            self.meterDecay = decay

        def GetMeterLevel(self):
            return self.meterLevel

    class Buttons:
        _buttonList = [
            'Ch1Rec',
            'Ch2Rec',
            'Ch3Rec',
            'Ch4Rec',
            'Ch5Rec',
            'Ch6Rec',
            'Ch7Rec',
            'Ch8Rec',

            'Ch1Solo',
            'Ch2Solo',
            'Ch3Solo',
            'Ch4Solo',
            'Ch5Solo',
            'Ch6Solo',
            'Ch7Solo',
            'Ch8Solo',

            'Ch1Mute',
            'Ch2Mute',
            'Ch3Mute',
            'Ch4Mute',
            'Ch5Mute',
            'Ch6Mute',
            'Ch7Mute',
            'Ch8Mute',

            'Ch1Sel',
            'Ch2Sel',
            'Ch3Sel',
            'Ch4Sel',
            'Ch5Sel',
            'Ch6Sel',
            'Ch7Sel',
            'Ch8Sel',

            'Ch1Enc',
            'Ch2Enc',
            'Ch3Enc',
            'Ch4Enc',
            'Ch5Enc',
            'Ch6Enc',
            'Ch7Enc',
            'Ch8Enc',

            'Track',
            'Send',
            'PanSurr',
            'PlugIn',
            'EQ',
            'Inst',

            'BankLeft',
            'BankRight',
            'ChannelLeft',
            'ChannelRight',

            'Flip',
            'Global',

            'Name/Value',
            'Beats',

            'F1',
            'F2',
            'F3',
            'F4',
            'F5',
            'F6',
            'F7',
            'F8',

            'MIDITracks',
            'Inputs',
            'AudioTracks',
            'AudioInst',
            'Aux',
            'Buses',
            'Outputs',
            'User',

            'Shift',
            'Option',
            'Control',
            'Alt',

            'Read',
            'Write',
            'Trim',
            'Touch',
            'Latch',
            'Group',

            'Save',
            'Undo',
            'Cancel',
            'Enter',

            'Marker',
            'Nudge',
            'Cycle',
            'Drop',
            'Replace',
            'Click',
            'Solo',

            'Rewind',
            'FastForward',
            'Stop',
            'Play',
            'Record',

            'Up',
            'Down',
            'Left',
            'Right',
            'Zoom',
            'Scrub',

            '_',
            '_',

            'Ch1Touch',
            'Ch2Touch',
            'Ch3Touch',
            'Ch4Touch',
            'Ch5Touch',
            'Ch6Touch',
            'Ch7Touch',
            'Ch8Touch',
            'MainTouch',

            'SMPTELED',
            'BeatsLED',
            'SoloLED'
        ]

        _usbbuttonList = [
            'Ch1Rec',
            'Ch2Rec',
            'Ch3Rec',
            'Ch4Rec',
            'Ch5Rec',
            'Ch6Rec',
            'Ch7Rec',
            'Ch8Rec',

            'Ch1Solo',
            'Ch2Solo',
            'Ch3Solo',
            'Ch4Solo',
            'Ch5Solo',
            'Ch6Solo',
            'Ch7Solo',
            'Ch8Solo',

            'Ch1Mute',
            'Ch2Mute',
            'Ch3Mute',
            'Ch4Mute',
            'Ch5Mute',
            'Ch6Mute',
            'Ch7Mute',
            'Ch8Mute',

            'Ch1Sel',
            'Ch2Sel',
            'Ch3Sel',
            'Ch4Sel',
            'Ch5Sel',
            'Ch6Sel',
            'Ch7Sel',
            'Ch8Sel',

            'Ch1Enc',
            'Ch2Enc',
            'Ch3Enc',
            'Ch4Enc',
            'Ch5Enc',
            'Ch6Enc',
            'Ch7Enc',
            'Ch8Enc',

            'Track',
            'Send',
            'PanSurr',
            'PlugIn',
            'EQ',
            'Inst',

            'BankLeft',
            'BankRight',
            'ChannelLeft',
            'ChannelRight',

            'Flip',
            'Global',

            'Name/Value',
            'Beats',

            'F1',
            'F2',
            'F3',
            'F4',
            'F5',
            'F6',
            'F7',
            'F8',

            'MIDITracks',
            'Inputs',
            'AudioTracks',
            'AudioInst',
            'Aux',
            'Buses',
            'Outputs',
            'User',

            'Shift',
            'Option',
            'Control',
            'Alt',

            'Read',
            'Write',
            'Trim',
            'Touch',
            'Latch',
            'Group',

            'Save',
            'Undo',
            'Cancel',
            'Enter',

            'Marker',
            'Nudge',
            'Cycle',
            'Drop',
            'Replace',
            'Click',
            'Solo',

            'Rewind',
            'FastForward',
            'Stop',
            'Play',
            'Record',

            'Up',
            'Down',
            'Left',
            'Right',
            'Zoom',
            'Scrub',

            '_',
            '_',

            'Ch1Touch',
            'Ch2Touch',
            'Ch3Touch',
            'Ch4Touch',
            'Ch5Touch',
            'Ch6Touch',
            'Ch7Touch',
            'Ch8Touch',
            'MainTouch',

            'SMPTELED',
            'BeatsLED',
            'SoloLED'
        ]

        class LEDState(Enum):
            Off = 0
            Blinking = 1
            On = 127

        class Button():
            def __init__(self, parent, index):
                self.parent = parent
                self.index = index
                self._pressed = False
                self.onChange = None
                self.onDown = None
                self.onUp = None
                self.state = self.parent.LEDState.Off

            def setOnChange(self, callback):
                self.onChange = callback

            def setOnDown(self, callback):
                self.onDown = callback

            def setOnUp(self, callback):
                self.onUp = callback

            @property
            def name(self):
                if self.parent.xtouch.usb_enabled:
                    return self.parent._usbbuttonList[self.index]
                else:
                    return self.parent._buttonList[self.index]

            @property
            def pressed(self):
                return self._pressed

            @pressed.setter
            def pressed(self, value):
                if value != self._pressed:
                    if self.onChange:
                        self.onChange(self)

                    if value and self.onDown:
                        self.onDown(self)

                    if not value and self.onUp:
                        self.onUp(self)

                self._pressed = value

            def SendLED(self):
                self.parent.xtouch.SendButton(self.index, self.state.value)

            def SetLED(self, state: bool):#: LEDState):
                self.state = self.parent.LEDState.On if state else self.parent.LEDState.Off
                self.SendLED()

            def BlinkLED(self):
                self.state = self.parent.LEDState.Blinking
                self.SendLED()

        def __init__(self, parent):
            self.xtouch = parent
            self.buttons = []

            for i in range(len(self._buttonList)):
                self.buttons.append(self.Button(self, i))

        def SetAllLEDs(self, state: LEDState):
            for b in self.buttons:
                b.SetLED(state)

        def GetButton(self, name: str):
            return self.buttons[self._buttonList.index(name)]






