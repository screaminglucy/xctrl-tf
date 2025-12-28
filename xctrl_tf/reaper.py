import reapy
import logging
import sys
import time
import threading
import _thread
import queue
import math

#reapy.print("Hello world!")
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)
WAIT_TIME = 0.010

def fader_db_to_value (gain_db): #1.0 = 0dB
    """Converts dB gain to linear amplitude/voltage gain ratio."""
    value = 10**(gain_db / 20.0)
    logger.debug ("fader_db_to_value "+str(value))
    return value


def fader_value_to_db (gain_ratio):
    if gain_ratio <= 0:
        # Logarithm of zero or a negative number is undefined
        return float('-inf') 
    # Formula: dB = 20 * log10(gain_ratio)
    db = 20 * math.log10(gain_ratio)
    logger.debug ("fader_value_to_db gain="+str(gain_ratio)+" db " +str(db))
    return db

class reaper:
    def __init__(self):
        self.project = reapy.Project()
        self._active = True
        self.lastSend = time.time()

    def getFaderName (self, channel):
        track = self.project.tracks[channel]
        name = track.name
        logger.debug ('track '+str(channel)+ " name "+name)
        return name
    
    def setFaderName (self, channel, name):
        track = self.project.tracks[channel]
        track.name = name
        logger.debug ('track '+str(channel)+ "set name "+name)
        return name
    
    def getFaderColor (self, channel):
        track = self.project.tracks[channel]
        name = track.color
        logger.debug ('track '+str(channel)+ " color "+str(name)) #0-255 rgb
        return name

    def setFaderColor (self, channel, color):
        track = self.project.tracks[channel]
        # Convert RGB to REAPER's native color format
        # The '0' argument is for a custom color flag
        r = color >> 16
        g = (color >> 8) & 0xff
        b = color & 0xff
        native_color = (r, g, b)
        track.color = native_color
        logger.debug ('track '+str(channel)+ " color "+str(native_color)) #0-255 rgb
    
    def getChannelSoloOn (self, channel):
        track = self.project.tracks[channel]
        name = track.is_solo
        logger.debug ('track '+str(channel)+ " solo "+str(name))
        return name
    
    def sendChannelMute (self, channel,mute):
        track = self.project.tracks[channel]
        track.is_muted = mute
        logger.debug ('track '+str(channel)+ " mute "+str(mute))
    
    def getChannelOn (self, channel):
        track = self.project.tracks[channel]
        name = track.is_muted
        logger.debug ('track '+str(channel)+ " mute "+str(name))
        return ~name
    
    def getFaderValue (self, channel):
        track = self.project.tracks[channel]
        name = track.get_info_value("D_VOL")
        logger.debug ('track '+str(channel)+ " value "+str(name)) #1.0 = 0dB
        return name
    
    def sendFaderValue (self, channel, db):
        logger.debug ("sendFaderValue()")
        if (time.time() - self.lastSend) > WAIT_TIME:
            logger.debug ('track '+str(channel)+ " value "+str(db)+"db") #1.0 = 0dB
            track = self.project.tracks[channel]
            v = fader_db_to_value(db)
            track.set_info_value("D_VOL",v)
            self.lastSend = time.time()
    
    def showDisconnected (self):
        reapy.print("TF mixer disconnect")

    def showConnected (self):
        reapy.print("TF mixer connected")
        
    def showSynced (self):
        reapy.print("synced to TF mixer ")

    def getMainFaderValue (self):
        master = self.project.master_track
        volume = master.get_info_value("D_VOL")
        logger.debug ('master vol '+str(volume)) #1.0 = 0dB
        return volume

    def sendMainFaderValue (self, db):
        v = fader_db_to_value(db) 
        master = self.project.master_track
        master.set_info_value("D_VOL",v)
        logger.debug ('set master vol '+str(v))

    