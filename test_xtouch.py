import XTouch.XTouchControls as XTouch

xtouch = XTouch.xtouch


xtouch.SendSlider(0,8192)
xtouch.SendScribble(0, "hi", "there", 6, False)

input("Press enter...")
xtouch.SendMeter(0,8)
input("Press enter...")