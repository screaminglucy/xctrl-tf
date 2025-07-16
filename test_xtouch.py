import xctrl_tf.XTouch as XTouch
import keyboard
import time
xtouch_ip = '192.168.10.9'
xtouch = XTouch.XTouch(xtouch_ip)
#set MIXER:Current/InCh/Fader/On [x] 0 [y]

while (xtouch._active == False):
    time.sleep(1)
    print ("waiting...")

xtouch.SendSlider(0,8192)
xtouch.SendScribble(0, "hi", "there", 6, False)
xtouch.SendScribble(1, "hi", "there2", 5, False)


input("Press enter...")

#tf.send_command(cmd)
while not keyboard.is_pressed('q'):
    xtouch.SetMeterLevel(0,8)
    time.sleep(2)
    xtouch.SetMeterLevel(1,7)
    time.sleep(2)
    xtouch.SetMeterLevel(2,6)
    time.sleep(2)
    xtouch.SetMeterLevel(3,5)
    time.sleep(2)
    xtouch.SetMeterLevel(4,4)
    time.sleep(2)
    xtouch.SetMeterLevel(5,3)
    time.sleep(2)
    xtouch.SetMeterLevel(6,2)
    time.sleep(2)
    xtouch.SetMeterLevel(7,1)
    time.sleep(2)
xtouch.running = False