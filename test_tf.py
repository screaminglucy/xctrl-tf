
import xctrl_tf.XTouch as XTouch
import xctrl_tf.tf as tf

input("Press enter...")
db = -35
print ('db '+str(db))
cmd = 'set MIXER:Current/InCh/Fader/Level 0 0 '+tf.fader_db_to_value(db) 
tf.send_command(cmd)
input("Press enter...")