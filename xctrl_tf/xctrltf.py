import XTouch as XTouch
import tf as tf
import time
import keyboard


class xctrltf:

    def __init__(self, xtouch_ip='192.168.10.9'):
        self.t = tf.tf_rcp()
        self.xtouch = XTouch.XTouch(xtouch_ip)
        self.wait_for_connect()
        self.xtouch.setOnButtonChange(XTouch.PrintButton)
        self.xtouch.GetButton('Flip').setOnChange(XTouch.PrintFlip)
        self.xtouch.GetButton('Flip').setOnDown(XTouch.FlipPress)
        self.xtouch.GetButton('Flip').setOnUp(XTouch.FlipRelease)
        self.xtouch.setOnSliderChange(self.updateTFFader)
        self.xtouch.SendSlider(0,8192)
        self.xtouch.SendScribble(0, "hi", "there", 6, False)

    def wait_for_connect (self):
        while (self.xtouch._active == False) and (self.t._active == False):
            time.sleep(1)
            print ("waiting to connect...")

    def updateTFFader (index,value):
        db = XTouch.fader_value_to_db(value)
        cmd = 'set MIXER:Current/InCh/Fader/Level '+str(index)+' 0 '+tf.fader_db_to_value(db) 
        t.send_command(cmd)


    def stop_running (self):
        self.xtouch.running = False
        self.t.running = False



x2tf = xctrltf()
input("Press enter to quit...")



