import time
import reaper
import logging
import _thread
import tf
from enum import Enum

global reaperObj
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

class Color(Enum):
    Off = 0x000000
    Red = 0xff0000
    Green = 0x00ff00
    Yellow = 0xffff00
    Blue = 0x0000ff
    Pink = 0xff007f
    Cyan = 0x00ffff
    White = 0xffffff
    Purple = 0x7f00ff
    SkyBlue = 0x0080ff0
    Orange = 0xffa500

def tfColor2Reaper (color):
    try:
        color = Color[color].value
    except:
        logging.error ("Color not found")
        return 0x000000
    return color

def onFaderNameRcv (chan, name):
    reaperObj.r.setFaderName(chan,name)
    reaperObj.fader_names[chan] = name

def onFaderColorRcv (chan, color):
    c = tfColor2Reaper (color)
    reaperObj.r.setFaderColor(chan,c)
    reaperObj.fader_colors[chan] = color

def onChannelMasterMute(chan, value):
    value =  not value
    if chan not in reaperObj.post_on_chan_list:
        reaperObj.r.sendChannelMute(chan,value)
      
global timeLastShown
timeLastShown = 0
def onTFdisconnected():
    global timeLastShown
    if (time.time() - timeLastShown) > 60:
        reaperObj.r.showDisconnected()
        timeLastShown = time.time()

class reaperClass:
    def __init__(self, tf_ip='192.168.10.10'):
        self.post_on_chan_list = [25,26,27,28,29,30,31]
        self.updateCounter = 0
        self.pendingDisplayUpdate = True
        self.t = None
        self.fader_names = ['uninitialized']*32
        self.fader_colors = ['uninitialized']*32
        self.mute_init = ['uninitialized']*32
        self.r = reaper.reaper()
        #unmute post on channels
        for ch in self.post_on_chan_list:
            self.r.sendChannelMute (ch,False)
        self.t = tf.tf_rcp(tf_ip)
        self.connected = False
        if self.t is not None:
            self.t.onTFdisconnected = onTFdisconnected
            self.t.onFaderColorRcv = onFaderColorRcv
            self.t.onFaderNameRcv = onFaderNameRcv
            self.t.onChannelMasterMute = onChannelMasterMute
        self.running = True
        _thread.start_new_thread(self.periodicSync, ())
        self.connected = True

    def syncTF2Reaper(self):
        _thread.start_new_thread(self.syncTF2Reaper_thread, ())

    def syncTF2Reaper_thread (self):
        self.updateCounter = self.updateCounter + 1
        for i in range(32):
            if self.updateCounter == 2:
                if self.fader_names[i] == 'uninitialized':
                    self.t.getFaderName(i)
                    time.sleep(0.001)
                if self.mute_init[i] == 'uninitialized':
                    if i not in self.post_on_chan_list:
                        self.t.getChannelOn(i)
                        time.sleep(0.001)
                if self.fader_colors[i] == 'uninitialized':
                    self.t.getFaderColor(i)
                while self.t.isQueueEmpty() == False:
                    time.sleep(0.02)
            
            time.sleep(0.001)
            while self.t.isQueueEmpty() == False:
                time.sleep(0.02)
        while self.t.isQueueEmpty() == False:
            time.sleep(0.02)
        self.t.getGlobalFxMute()
        while self.t.isQueueEmpty() == False:
            time.sleep(0.01)
        if self.updateCounter == 2:
            self.updateCounter = 0
        logger.info ("syncTF2Reaper()")

   
    def periodicSync(self):
        while self.running:
            if self.connected:      
                #self.r.refreshSurfaces()
                loop_start_time = time.time()
                while (self.t.isQueueEmpty() == False):
                    time.sleep(0.1)
                self.syncTF2Reaper()
                if 'uninitialized' in self.fader_colors or 'uninitialized' in self.fader_names:
                    time.sleep(2)
                else:
                    time.sleep(2)
                wait_time = 0
                while ((time.time() - loop_start_time) < wait_time):
                    time.sleep(0.5)
                    


    def stop_running (self):
        self.t.running = False
        self.running = False

    

running = True
print ('waiting 30 sec to start to allow reaper to load')
reaperObj = reaperClass()
firstSync = True
synced = False
while running:
    time.sleep(1)
    if reaperObj.r._active:
        if firstSync:
            firstSync = False
            synced = True
            logger.info ("Finished syncing")
    else:
        synced=False
reaperObj.stop_running()


