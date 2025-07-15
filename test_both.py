import xctrl_tf.XTouch as XTouch
import xctrl_tf.tf as tf
import time
import keyboard

t = tf.tf
xtouch = XTouch.xtouch
#set MIXER:Current/InCh/Fader/On [x] 0 [y]

while (xtouch._active == False):
    time.sleep(1)
    print ("waiting...")

while (t._active == False):
    time.sleep(1)
    print ("waiting...")

xtouch.SendSlider(0,8192)
xtouch.SendScribble(0, "hi", "there", 6, False)



input("Press enter...")
db = XTouch.fader_value_to_db(XTouch.current_value_fader_zero)
print ('db '+str(db))
cmd = 'set MIXER:Current/InCh/Fader/Level 0 0 '+tf.fader_db_to_value(db) 
t.send_command(cmd)
xtouch.SendMeter(0,8)

cmd = 'mtrstart MIXER:Current/InCh/PreHPF 100' #time interval
t.send_command(cmd)
cmd = 'mtrstart MIXER:Current/Mix/PreEQ 100' #time interval
t.send_command(cmd)


input("Press enter...")


#keep alive "devstatus runmode"
print("Looping... Press 'q' to quit.")

while not keyboard.is_pressed('q'):
    # Your code to be executed repeatedly goes here
    time.sleep(0.01)  # Add a small delay to prevent excessive CPU usage
    db = XTouch.fader_value_to_db(XTouch.current_value_fader_zero)
    XTouch.fader_db_to_value (db)
    print ('******************db '+str(db))
    cmd = 'set MIXER:Current/InCh/Fader/Level 0 0 '+tf.fader_db_to_value(db) 
    t.send_command(cmd)

xtouch.running = False
t.running = False

