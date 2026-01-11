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

def onFaderColorRcv (chan, color):
    c = tfColor2Reaper (color)
    reaperObj.r.setFaderColor(chan,c)

def onChannelMasterMute(chan, value):
    value =  not value
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
        self.pendingDisplayUpdate = True
        self.t = None
        self.r = reaper.reaper()
        for i in range(32):
            self.r.setFaderName (i,"ch "+str(i+1))
            #c = tfColor2Reaper ("Blue")
            #self.r.setFaderColor(i,c)
            #self.r.sendChannelMute(i,False)
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
        for i in range(32):
            self.t.getFaderName(i)
            self.t.getFaderColor(i)
            while self.t.isQueueEmpty() == False:
                time.sleep(0.01)
            self.t.getChannelOn(i)
            while self.t.isQueueEmpty() == False:
                time.sleep(0.01)
        while self.t.isQueueEmpty() == False:
            time.sleep(0.01)
        self.t.getGlobalFxMute()
        while self.t.isQueueEmpty() == False:
            time.sleep(0.01)
        logger.info ("syncTF2Reaper()")

   
    def periodicSync(self):
        while self.running:
            if self.connected:      
                loop_start_time = time.time()
                while (self.t.isQueueEmpty() == False):
                    time.sleep(0.1)
                self.syncTF2Reaper()
                wait_time = 10
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


