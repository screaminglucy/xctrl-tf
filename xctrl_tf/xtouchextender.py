import mido

from enum import Enum
from datetime import datetime
import threading
import _thread
import socket
from time import sleep
import sys
import logging
import math
import time
import queue
import inspect

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

#USB MCU mode (mackie control)
#Tested with Behringer XTouch Extender but since it's mackie control in theory any USB mackie control surface would work
#by adjusting the device byte for scribble strips sysex message
#relevant doc: https://htlab.net/computer/protocol/mackie-control/MackieControlProtocol_EN.pdf

class XTouchExt:

    def __init__(self, midiname='X-Touch-Ext', device="X-Touch-Extender"):
        self.name = midiname
        self.running = False
        self._active = False
        self.counter = 0
        self.device = device
        self.input_port = None
        self.output_port = None
        self.outbound_q = queue.Queue()
        self.channels = []
        for i in range(9):
            self.channels.append(self.ExtChannel(self, i))
        self.buttons = self.Buttons(self)
        self.onButtonChange = None
        self.onSliderChange = None
        self.onEncoderChange = None
        self._active = False
        self.lastMsgTime = None
        self.connect()

    def fader_value_to_db (self, value):
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

    def fader_db_to_value (self, db):
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

    def connect(self):
        logger.info ("Connect")
        in_port_name = self.name
        out_port_name = self.name
        try:
            ins = mido.get_input_names()
            outs = mido.get_output_names()
            for i in ins:
                if self.name in i:
                    in_port_name = i
            for o in outs:
                if self.name in o:
                    out_port_name = o
            self.output_port = mido.open_output(out_port_name)
            self.input_port = mido.open_input(in_port_name)
            self.running = True
            _thread.start_new_thread(self.getMsg, ())
            _thread.start_new_thread(self.processOutgoingPackets, ())
            logger.info("Midi connection opened")
        except OSError as e:
            logger.error(f"Error opening MIDI port: {e}")
            self.running = False

    def getMsg(self):
        while self.running:
            if self.input_port is not None:
                msg = self.input_port.receive(block=True)
                self._active = True
                self.HandleMsg(msg)
                self.lastMsgTime = time.time() 
    
    def processOutgoingPackets (self):
        logger.info ("xtouch processOutgoingPackets() thread started")
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

    def sendRawMsg(self, msg):
        if self.running:
            #if msg.type == 'control_change':
                #if msg.control == 80:
                    #logger.info (str(msg))
                    # Get the current frame and then the frame of the caller
                    #caller_frame = inspect.currentframe().f_back
                    # Get the code object of the caller's frame and its name
                    #caller_name = caller_frame.f_code.co_name
                    #print(f"callee_function was called by: {caller_name}")
            self.outbound_q.put(msg)
        

    def SendAll(self):
        for c in self.channels:
            c.SendAll()
        for b in self.buttons:
            self.SendButton(b)

    def SendButton(self, index, value):
        msg = mido.Message ('note_on', note=index, velocity = value )
        self.sendRawMsg(msg)

    def SendSlider(self, index, value):
        msg = mido.Message('pitchwheel', channel=index, pitch=value)
        self.sendRawMsg(msg)

    def SendEncoder(self, index, value):
        #left = ''.join(['1' if v else '0' for v in values][:7])
        #right = ''.join(['1' if v else '0' for v in values][7:])
        #logger.debug('left '+ str(left))
        #logger.debug('right '+ str(right))
        #logger.debug ('values '+str(values))
        # input is 0 to +12
        value = value - 1
        if value < 0:
            value = 0
        value = 0x20 | value
        msg = mido.Message('control_change', control=48+index, value=value)
        logger.debug (str(msg))
        self.sendRawMsg(msg)


    '''
    The colors of the entire unit LCD are set with a single Sysex message. The message is as follows:
    Full size XTouch (all scribbles red)
    F0 00 00 66 14 72 01 01 01 01 01 01 01 01 F7
    Extender (all scribbles red):
    F0 00 00 66 15 72 01 01 01 01 01 01 01 01 F7

    All Sysex messages begin with F0 and end with F7, those are not special. The first 5 bytes after the F0 (00 00 66 14 72) are required. The next 8 bytes are what set the colors of each scribble (in order from left to right), followed by F7. The colors are mapped as follows:

    00 - Blank
    01 - Red
    02 - Green
    03 - Yellow
    04 - Blue
    05 - Purple
    06 - Cyan
    07 - White

    Displaying Data on LCD
    DAW -> controller

    Every LCD message start with the header followed by the 0x12 byte.
    Then the next byte tells the position to display the text.
    We get the actual text (mostly 6 chars)
    Finally, the SysEx ends with a 0xF7 byte
    Example:

    F0 00 00 66 00 12 38 ***4C 35 30 52 35 30 20*** FC
    <hdr>         |   _position                     _end of SysEx
            LCD message
    Position of the text on the LCD
    On a Mackie Control, the LCD screen has 2x56 characters, divided by 8 (8 channels on a BCF2000) equals 7 chars by channel.

    Each position on the screen is identified by an offset:

    From 00 to 37 (56 values) for the first line,
    From 38 to 6F (56 values) for the second line
    '''

    def SendScribble(self, index, topText, bottomText, color, bottomInverted):
        self.channels[index].scribbleColor = color 
        deviceByte = 0x15
        if self.device != "X-Touch-Extender":
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

    def SendMeter(self, index, level):
        #self.SendMeters()
        msg = mido.Message('aftertouch',value=(index<<4)|level)
        self.sendRawMsg(msg)

    def SendMeters(self):
        #msg = mido.Message('control_change', control=90+index, value=value)
        #self.sendRawMsg(bytearray([0xF0, 0xD0, 0x00, 0 + self.channels[0].GetMeterLevel(), 16 + self.channels[1].GetMeterLevel(), 32 + self.channels[2].GetMeterLevel() , 48 + self.channels[3].GetMeterLevel(), 64 + self.channels[4].GetMeterLevel(), \
        #80 + self.channels[5].GetMeterLevel(), 96 + self.channels[6].GetMeterLevel(), 112 + self.channels[7].GetMeterLevel(),0xF7]))
        for i in range (8):
            self.SendMeter(i,self.channels[i].GetMeterLevel())
  
    def SetMeterLevel(self, channel, level):
        self.channels[channel].SetMeterLevel(level)

    def SetMeterLevelPeak(self, channel, level):
        self.channels[channel].SetMeterLevelPeak(level)
    
    def HandleMsg(self, data):
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
            if note >= 104 and note <= 112:
                note = note - 104 + 40
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
            


    def GetButton(self, name: str):
        return self.buttons.GetButton(name)


    class ExtChannel:
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
            enc = self.encoderValue
            logger.debug (' encoderValue ' + str(self.encoderValue))
            #if self.encoderFromCenter:
            #    values = [enc>=0, enc >= -1, enc >= -2, enc >= -3, enc >= -4, enc >= -5, enc >= -6, enc >= 6, enc >= 5, enc >= 4, enc >= 3, enc >= 2, enc >= 1]
            #elif self.encoderBetween:
            #    values = [enc <= -5.25, enc >= -5.75 and enc <= -4.25, enc >= -4.75 and enc <= -3.25, enc >= -3.75 and enc <= -2.25, enc >= -2.75 and enc <= -1.25, enc >= -1.75 and enc <= -0.25, enc >= -0.75 and enc <= 0.75, enc >= 0.25 and enc <= 1.75, enc >= 1.25 and enc <= 2.75, enc >= 2.25 and enc <= 3.75, enc >= 3.25 and enc <= 4.75, enc >= 4.25 and enc <= 5.75, enc >= 5.25]
            #else:
            #    values =  [enc < -5.5, enc >= -5.5 and enc < -4.5, enc >= -4.5 and enc < -3.5, enc >= -3.5 and enc < -2.5, enc >= -2.5 and enc < -1.5, enc >= -1.5 and enc < -0.5, enc >= -0.5 and enc < 0.5, enc >= 0.5 and enc < 1.5, enc >= 1.5 and enc < 2.5, enc >= 2.5 and enc < 3.5, enc >= 3.5 and enc < 4.5, enc >= 4.5 and enc < 5.5, enc >= 5.5]
            enc = enc + 6 #make positive
            self.xtouch.SendEncoder(self.index, int(enc))
            logger.debug ('encoder:'+str(self.index)+'  value = '+ str(enc))
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

            'Ch1Touch',
            'Ch2Touch',
            'Ch3Touch',
            'Ch4Touch',
            'Ch5Touch',
            'Ch6Touch',
            'Ch7Touch',
            'Ch8Touch',
            
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

def PrintButton(button):
    logger.info('%s (%d) %s' % (button.name, button.index, 'pressed' if button.pressed else 'released'))
    button.SetLED(button.pressed)

def PrintFlip(button):
    logger.info('FLIP %s' % ('PRESSED' if button.pressed else 'RELEASED'))

def FlipPress(button):
    logger.info('PRESSED FLIP')

def FlipRelease(button):
    logger.info('RELEASED FLIP')


def SetAllSliders(index, value):
    xtouch.SendScribble(index, '', '', 5, False)
    for i in range(9):
        if i != index:
            xtouch.SendSlider(i, value)
            xtouch.SendScribble(i, '', '', 7, False)


