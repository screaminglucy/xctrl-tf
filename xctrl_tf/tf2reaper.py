import time
import reaper
import logging
import _thread
import tf

global reaperObj
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

def onFaderNameRcv (chan, name):
    reaperObj.updateFaderName(chan,name)

def onFaderColorRcv (chan, color):
    reaperObj.updateFaderColor(chan,color)

def onFaderIconRcv (chan, icon):
    reaperObj.updateFaderIcon(chan,icon)

def onChannelMasterMute(chan, value):
    value =  not value
    reaperObj.updateChannelMute(chan,value)
      
def onTFdisconnected():
    reaperObj.showDisconnected()

class reaperClass:
    def __init__(self, tf_ip='192.168.10.10'):
        self.pendingDisplayUpdate = True
        self.t = None
        for i in range(32):
            self.r.updateFaderName (i,"channel "+str(i+1))
        self.t = tf.tf_rcp(tf_ip)
        self.r = reaper.reaper()
        self.connected = False
        if self.t is not None:
            self.t.onTFdisconnected = onTFdisconnected
            self.t.onFaderColorRcv = onFaderColorRcv
            self.t.onFaderNameRcv = onFaderNameRcv
            self.t.onChannelMasterMute = onChannelMasterMute
        self.running = True
        self.sync2TF()
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

   
    def periodicDisplayRefresh(self):
        while self.running:
            k = 0
            j = 0
            if self.connected:      
                loop_start_time = time.time()
                while (self.t.isQueueEmpty() == False):
                    time.sleep(0.1)
                self.syncTF2Reaper()
                wait_time = 5
                while ((time.time() - loop_start_time) < wait_time):
                    time.sleep(0.5)
                    
    def updateFaderColor(self,chan,value):
        
        if value == "Purple":
            color = 5 #pink
            logger.debug (value + " no color match using pink!")
        elif value == "SkyBlue":
            color = 6 #cyan
            logger.debug (value + " no color match using cyan!")
        else:
            color = 7
            logger.debug (value + " no color match using white!")
        if color == 0: #we dont want any "off"
            color = 7
        self.fader_colors[chan] = color

    def stop_running (self):
        self.t.running = False
        self.running = False

    

running = True


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


