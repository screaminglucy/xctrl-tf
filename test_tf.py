import time
import xctrl_tf.tf as tf

t = tf.tf

while (t._active == False):
    time.sleep(1)
    print ("waiting...")

input("Press enter...")
db = -35
print ('db '+str(db))
cmd = 'set MIXER:Current/InCh/Fader/Level 0 0 '+tf.fader_db_to_value(db) 
t.send_command(cmd)
input("Press enter...")
t.running = False