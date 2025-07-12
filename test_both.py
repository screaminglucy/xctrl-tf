import xctrl_tf.XTouch as XTouch
import xctrl_tf.tf as tf
import time

xtouch = XTouch.xtouch
#set MIXER:Current/InCh/Fader/On [x] 0 [y]

while (xtouch._active == False):
    time.sleep(1)
    print ("waiting...")

xtouch.SendSlider(0,8192)
xtouch.SendScribble(0, "hi", "there", 6, False)



input("Press enter...")
db = XTouch.fader_value_to_db(XTouch.current_value_fader_zero)
print ('db '+str(db))
cmd = 'set MIXER:Current/InCh/Fader/Level 0 0 '+tf.fader_db_to_value(db) 
tf.send_command(cmd)
xtouch.SendMeter(0,8)
input("Press enter...")
xtouch.running = False