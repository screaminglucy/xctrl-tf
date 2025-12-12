import reapy
import logging
import sys
import time
import threading
import _thread
import queue


#reapy.print("Hello world!")
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)
#is_muted
#is_solo

class reaper:
    def __init__(self):
        self.project = reapy.Project()
        self._active = True

    def getFaderName (self, channel):
        track = self.project.tracks[channel]
        name = track.name
        logger.info ('track '+str(channel)+ " name "+name)
        return name
    
    def getFaderColor (self, channel):
        track = self.project.tracks[channel]
        name = track.color
        logger.debug ('track '+str(channel)+ " color "+str(name))
        return name
    
    def getChannelSoloOn (self, channel):
        track = self.project.tracks[channel]
        name = track.is_solo
        logger.debug ('track '+str(channel)+ " solo "+str(name))
        return name
    
    def getChannelOn (self, channel):
        track = self.project.tracks[channel]
        name = track.is_muted
        logger.debug ('track '+str(channel)+ " mute "+str(name))
        return ~name
    
    def getFaderValue (self, channel):
        track = self.project.tracks[channel]
        name = track.get_info_value("D_VOL")
        logger.debug ('track '+str(channel)+ " name "+str(name))
        return name

