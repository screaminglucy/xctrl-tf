import sys
import socket
import time
import logging
import threading
import _thread
from tfmeter import meter_dict
import queue
from uuid import getnode as get_mac
import binascii

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

def fader_db_to_value (db):
    value = int(db * 100)
    logger.debug ("fader_db_to_value "+str(value))
    return str(value)
   # Max Fader Value: 1000
   #Min Fader Value: -13800
   #Negative Infinity Value: -32768

def fader_value_to_db (value):
    db = value / 100
    return db

def get_mac_addr():
    mac_int = get_mac()
    mac_address = ':'.join(("%012X" % mac_int)[i:i+2] for i in range(0, 12, 2))
    print(f"my MAC Address: {mac_address}")
    return mac_address

def get_ip():
  """Retrieves the local IP address of the machine."""
  hostname = socket.gethostname()
  local_ip = socket.gethostbyname(hostname)
  return local_ip

def detect_yamaha (timeout=30): 
    #send udp broadcast to probe for mixer
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) 
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) 
    ip = get_ip()
    mac_address_str = get_mac_addr()
    mac_address_hex = mac_address_str.replace(":", "").replace("-", "").lower()
    mac_address_bytearray = bytearray(binascii.unhexlify(mac_address_hex))
    logger.info ('my ip is '+ip)
    ip_bytes = socket.inet_aton(ip)
    message5 = b"YSDP\x00D\x00\x04"
    message5 += ip_bytes
    message5 += b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
    message5 += mac_address_bytearray
    message5 += b"\x08_ypax-tf\x00!\x12Yamaha Corporation\x03TF5\x09Yamaha TF"
    print(message5)
    message = b"YSDP\x00H\x00\x04"
    message += ip_bytes
    message += b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x18\xc0"
    message += mac_address_bytearray
    message += b"\x08_ypax-tf\x00%\x12Yamaha Corporation\x07TF-RACK\x09Yamaha TF"
    sock.bind(('', 54330))
    b = (ip.split('.'))[:-1]
    b.append('255')
    b = '.'.join(b)
    logger.info ('broadcast to ' + b)
    detect = False
    start = time.time()
    while detect == False and (time.time()-start) < timeout:
        sock.sendto(message, (b, 54330))
        sock.sendto(message5, (b, 54330))
        data, addr = sock.recvfrom(1024) # buffer size is 1024 bytes
        logger.debug("received message: %s" % data)
        data_list = list(data)
        logger.debug (data_list)
        ip = addr[0]
        if ip!=get_ip() and ip!='127.0.0.1':
            logger.info (ip)
            logger.info ('detected yamaha')
            detect = True
    if detect == False:
        logger.warning ("no yamaha auto detected")
        return None
    return ip
        

class tf_rcp:

    def __init__(self, ip=None):
        self.mix = 9 #aux9
        ip_detected = detect_yamaha()
        if ip_detected is None:
            self.host = ip
        else:
            self.host = ip_detected
        if self.host is None:
            logger.error ("no IP found or specified for yamaha")
        self.outbound_q = queue.Queue()
        self._active = False
        self.last_fader_updates = [time.time()]*40
        self.last_main_fader_update =  time.time()
        self.lastMsgTime = None
        self.onMixMeterRcv = None
        self.onChMeterRcv = None
        self.onFaderNameRcv = None
        self.onFXSendValueRcv = None
        self.onFaderColorRcv = None
        self.onFaderValueRcv = None
        self.onChannelMute = None
        self.onGlobalMuteRcv = None
        self.onMainFaderValueRcv = None
        self.onMainFXFaderValueRcv = None
        self.onFXSendEnValueRcv = None
        self.onFaderIconRcv = None
        self.onChannelMasterMute = None
        self.connect()

    def connect(self):
        self.sock = None
        self.port = 49280
        self.running = True
        _thread.start_new_thread(self.processOutgoingPackets, ())
        _thread.start_new_thread(self.maintain_connection, ())
        _thread.start_new_thread(self.HandleMsg, ())
        self.SendKeepAlive()
        self.Metering()
        logger.info("Starting try to connect")

    def maintain_connection(self):
        retry_interval = 1
        while self.running:
            start_time = time.time()
            logger.info ('maintain_connection: trying to connect')
            while self._active == False:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                try:
                    # Attempt to connect non-blocking
                    result = s.connect_ex((self.host, self.port))
                    if result == 0:  # Connection successful
                        logger.info(f"Successfully connected to {self.host}:{self.port}")
                        self.sock = s
                        self._active = True
                        self.lastMsgTime = time.time()
                        self.send_command('scpmode keepalive 10000')
                    else:
                        logger.info(f"Connection failed (Error: {errno.errorcode[result]}). Retrying...")
                        s.close()  # Close the socket before retrying
                except Exception as e:
                    logger.info(f"An error occurred: {e}. Retrying...")
                    s.close()
                if self._active == False:
                    time.sleep(retry_interval)
                    logger.info(f"Could not connect to {self.host}:{self.port}. Retry in 1 sec")          
            while self.running and self._active:
                time.sleep(5)
            self.sock.close()

    def SendKeepAlive(self, timeout=5):
        if self.running:
            if self._active:
                self.send_command("devstatus runmode")
            else:
                logger.info(f"Dropped connection from {self.host}")
            threading.Timer(1, self.SendKeepAlive).start()
            if self.lastMsgTime is not None:
                if ((time.time() - self.lastMsgTime) > timeout) and self._active:
                    logger.info(f"Dropped connection from {self.host}")
                    self._active = False
            

    def Metering(self):
        if self.running:
            if self._active:
                cmd = 'mtrstart MIXER:Current/InCh/PreHPF 400' #time interval
                self.send_command(cmd)
                cmd = 'mtrstart MIXER:Current/Mix/PreEQ 400' #time interval
                self.send_command(cmd)
            threading.Timer(10, self.Metering).start()
    
    def setOnChMeterRcv(self, callback):
        self.onChMeterRcv = callback

    def setOnMixMeterRcv(self, callback):
        self.onMixMeterRcv = callback

    def getFaderValue (self, channel):
        if self.mix == 0:
            cmd = 'get MIXER:Current/InCh/Fader/Level ' + str(channel)+' 0' 
        else:
            cmd = 'get MIXER:Current/InCh/ToMix/Level ' + str(channel)+' '+str(self.mix)+' '
        self.send_command(cmd)
        logger.debug ('sent '+cmd)

    def getMainFaderValue (self):
        if self.mix != 0:
            cmd = 'get MIXER:Current/Mix/Fader/Level '+ str(self.mix)+' 0' 
        else:
            cmd = 'get MIXER:Current/St/Fader/Level 0 0'
        self.send_command(cmd)

    def getMainFXFaderValue (self, fx):
        if self.mix != 0:
            cmd = 'get MIXER:Current/FxRtnCh/ToMix/Level '+ str(fx*2)+' '+str(self.mix) 
        else:
            cmd = 'get MIXER:Current/FxRtnCh/Fader/Level '+ str(fx*2)+' 0'
        self.send_command(cmd)

    def sendMainFXFaderValue (self, db, fx):
        v = fader_db_to_value(db) 
        if self.mix != 0:
            cmd = 'set MIXER:Current/FxRtnCh/ToMix/Level '+ str(fx*2)+ ' '+ str(self.mix)+' '+v 
        else:
            cmd = 'set MIXER:Current/FxRtnCh/Fader/Level '+ str(fx*2)+' 0 '+v
        if (time.time() - self.last_main_fader_update) > 0.100:
            self.send_command(cmd)
            self.last_main_fader_update = time.time() 

    def getFX1Send (self, channel):
        cmd = 'get MIXER:Current/InCh/ToFx/Level '+ str(channel)+ ' 0' 
        self.send_command(cmd)
        logger.debug ('sent '+cmd)
        cmd = 'get MIXER:Current/InCh/ToFx/On ' + str(channel) + ' 0'
        self.send_command(cmd)


    def getFX2Send (self, channel):
        cmd = 'get MIXER:Current/InCh/ToFx/Level '+ str(channel)+ ' 1' 
        self.send_command(cmd)
        logger.debug ('sent '+cmd)
        cmd = 'get MIXER:Current/InCh/ToFx/On ' + str(channel) + ' 1'
        self.send_command(cmd)

    def getFaderName (self, channel):
        cmd = 'get MIXER:Current/InCh/Label/Name ' + str(channel)+' 0' 
        self.send_command(cmd)
        logger.debug ('sent '+cmd)

    def getFaderColor(self,channel):
        cmd = 'get MIXER:Current/InCh/Label/Color ' + str(channel)+' 0' 
        self.send_command(cmd)
        logger.debug ('sent '+cmd)

    def getFaderIcon(self,channel):
        cmd = 'get MIXER:Current/InCh/Label/Icon ' + str(channel)+' 0' 
        self.send_command(cmd)
        logger.debug ('sent '+cmd)

    def getChannelOn(self,channel):
        cmd = 'get MIXER:Current/InCh/Fader/On ' + str(channel)+' 0 1' 
        self.send_command(cmd)
        if self.mix != 0:
            cmd = 'get MIXER:Current/InCh/ToMix/On ' + str(channel)+' '+str(self.mix)+' 1'
            self.send_command(cmd)
        logger.debug ('sent '+cmd)
    
    def sendFXSend(self,fx,channel,db):
        value = fader_db_to_value(db)
        if fx == 0:
            cmd = 'set MIXER:Current/InCh/ToFx/Level '+ str(channel)+ ' 0 ' + str(value) 
        else:
            cmd = 'set MIXER:Current/InCh/ToFx/Level '+ str(channel)+ ' 1 ' + str(value) 
        self.send_command(cmd)

    def sendGlobalFxMute (self, value):
        cmd = 'set MIXER:Current/MuteMaster/On 1 0 '
        if value:
            cmd += '1'
        else:
            cmd += '0'
        self.send_command(cmd)

    def getGlobalFxMute (self):
        cmd = 'get MIXER:Current/MuteMaster/On 1 0 '
        self.send_command(cmd)

    def sendChannelMute(self,channel,value):
        if self.mix == 0:
            cmd = 'set MIXER:Current/InCh/Fader/On ' + str(channel)+' 0 '
        else:
            cmd = 'set MIXER:Current/InCh/ToMix/On ' + str(channel)+' '+str(self.mix)+' '
        if value == True:
            cmd += '0'
        else:
            cmd += '1'
        self.send_command(cmd)

    def sendMainFaderValue (self, db):
        v = fader_db_to_value(db) 
        if self.mix != 0:
            cmd = 'set MIXER:Current/Mix/Fader/Level '+ str(self.mix)+' 0 '+v 
        else:
            cmd = 'set MIXER:Current/St/Fader/Level 0 0 '+v
        if (time.time() - self.last_main_fader_update) > 0.100:
            self.send_command(cmd)
            self.last_main_fader_update = time.time() 
    
    def sendFaderValue(self,chan, db, noConvert=False):
        v = fader_db_to_value(db) 
        if noConvert:
            v = str(db)
        if self.mix == 0:
            cmd = 'set MIXER:Current/InCh/Fader/Level '+str(chan)+' 0 '+v
        else: 
            cmd = 'set MIXER:Current/InCh/ToMix/Level '+str(chan)+' '+str(self.mix)+' '+v
        
        if (time.time() - self.last_fader_updates[chan]) > 0.100:
            self.send_command(cmd)
            self.last_fader_updates[chan] = time.time() 

    def HandleMsg (self):
        # receive a message 
        while self.running:
            buffer = b""
            if self._active:
                try:
                    data = self.sock.recv(1500)
                except:
                    data = None
                if data:
                    self.lastMsgTime = time.time()
                    buffer += data
                    if b"\n" in buffer:
                        index_of_char = buffer.find(b"\n")
                        if index_of_char != -1:
                            message = buffer[:index_of_char]
                            messageString = message.decode('utf-8')
                            if messageString.startswith('NOTIFY mtr MIXER:Current/Mix'):
                                if self.onMixMeterRcv:
                                    values = messageString.split(' ')[4:]
                                    self.onMixMeterRcv([meter_dict[int(numeric_string, 16)] for numeric_string in values]) 
                            elif messageString.startswith('NOTIFY mtr MIXER:Current/InCh'):
                                if self.onChMeterRcv:
                                    values = messageString.split(' ')[4:]
                                    self.onChMeterRcv([meter_dict[int(numeric_string, 16)] for numeric_string in values]) 
                            elif ((messageString.startswith('OK get MIXER:Current/InCh/Fader/Level') or messageString.startswith('NOTIFY set MIXER:Current/InCh/Fader/Level')) and self.mix == 0) or \
                                  ((messageString.startswith('OK get MIXER:Current/InCh/ToMix/Level') or messageString.startswith('NOTIFY set MIXER:Current/InCh/ToMix/Level')) and self.mix != 0) :
                                chan = int(messageString.split(' ')[3])
                                level = int(messageString.split(' ')[5])
                                if self.onFaderValueRcv:
                                    self.onFaderValueRcv(chan,level)
                            elif ((messageString.startswith('OK get MIXER:Current/Mix/Fader/Level') or messageString.startswith('NOTIFY set MIXER:Current/Mix/Fader/Level')) and self.mix != 0) or \
                                  ((messageString.startswith('OK get MIXER:Current/St/Fader/Level') or messageString.startswith('NOTIFY set MIXER:Current/St/Fader/Level')) and self.mix == 0) :
                                level = int(messageString.split(' ')[5])
                                if self.onMainFaderValueRcv:
                                    self.onMainFaderValueRcv(level)
                            elif ((messageString.startswith('OK get MIXER:Current/FxRtnCh/ToMix/Level') or messageString.startswith('NOTIFY set MIXER:Current/FxRtnCh/ToMix/Level')) and self.mix != 0) or \
                                  ((messageString.startswith('OK get MIXER:Current/FxRtnCh/Fader/Level') or messageString.startswith('NOTIFY set MIXER:Current/FxRtnCh/Fader/Level')) and self.mix == 0) :
                                fx_select = int (int(messageString.split(' ')[3]) / 2)
                                level = int(messageString.split(' ')[5])
                                if self.onMainFXFaderValueRcv:
                                    self.onMainFXFaderValueRcv(fx_select,level)
                            elif messageString.startswith('OK get MIXER:Current/InCh/ToFx/Level') or messageString.startswith('NOTIFY set MIXER:Current/InCh/ToFx/Level')  :
                                chan = int(messageString.split(' ')[3])
                                fx_select = int(messageString.split(' ')[4])
                                level = int(messageString.split(' ')[5])
                                if self.onFXSendValueRcv:
                                    self.onFXSendValueRcv(fx_select, chan,level)
                            elif messageString.startswith('OK get MIXER:Current/InCh/ToFx/On') or messageString.startswith('NOTIFY set MIXER:Current/InCh/ToFx/On')  :
                                chan = int(messageString.split(' ')[3])
                                fx_select = int(messageString.split(' ')[4])
                                on = int(messageString.split(' ')[5])
                                if self.onFXSendEnValueRcv:
                                    self.onFXSendEnValueRcv(fx_select, chan,on)
                            elif messageString.startswith('OK get MIXER:Current/InCh/Label/Name') or messageString.startswith('NOTIFY set MIXER:Current/InCh/Label/Name'):
                                chan = int(messageString.split(' ')[3])
                                name = messageString.split('"')[1]
                                if self.onFaderNameRcv:
                                    self.onFaderNameRcv(chan,name)
                            elif messageString.startswith('OK get MIXER:Current/InCh/Label/Color') or messageString.startswith('NOTIFY set MIXER:Current/InCh/Label/Color'):
                                logger.debug(messageString)
                                chan = int(messageString.split(' ')[3])
                                name = messageString.split('"')[1]
                                if self.onFaderColorRcv:
                                    self.onFaderColorRcv(chan,name)
                            elif messageString.startswith('OK get MIXER:Current/InCh/Label/Icon') or messageString.startswith('NOTIFY set MIXER:Current/InCh/Label/Icon'):
                                logger.debug(messageString)
                                chan = int(messageString.split(' ')[3])
                                icon = messageString.split('"')[1]
                                if self.onFaderIconRcv:
                                    self.onFaderIconRcv(chan,icon)
                            elif messageString.startswith('OK get MIXER:Current/MuteMaster/On 1 0') or messageString.startswith('NOTIFY set MIXER:Current/MuteMaster/On 1 0'):
                                logger.debug(messageString)
                                value = (int(messageString.split(' ')[5]) == 1)
                                if self.onGlobalMuteRcv:
                                    self.onGlobalMuteRcv(value)
                            elif ((messageString.startswith('OK get MIXER:Current/InCh/Fader/On') or messageString.startswith('NOTIFY set MIXER:Current/InCh/Fader/On')) and self.mix == 0) or \
                                  ((messageString.startswith('OK get MIXER:Current/InCh/ToMix/On') or messageString.startswith('NOTIFY set MIXER:Current/InCh/ToMix/On')) and self.mix != 0):
                                logger.debug(messageString)
                                chan = int(messageString.split(' ')[3])
                                value = int(messageString.split(' ')[5])
                                if value == 0:
                                    value = False
                                else:
                                    value = True
                                if self.onChannelMute:
                                    self.onChannelMute(chan,value)
                            elif ((messageString.startswith('OK get MIXER:Current/InCh/Fader/On') or messageString.startswith('NOTIFY set MIXER:Current/InCh/Fader/On')) and self.mix != 0):
                                chan = int(messageString.split(' ')[3])
                                value = int(messageString.split(' ')[5])
                                if value == 0:
                                    value = False
                                else:
                                    value = True
                                if self.onChannelMasterMute:
                                    self.onChannelMasterMute(chan,value)
                            elif messageString.startswith("ERROR"):
                                logger.error(f"Received: {message.decode()}")
                            else:
                                pass
                        #end of message received
                        buffer = buffer[index_of_char:]

    def processOutgoingPackets (self):
        logger.info ("tf processOutgoingPackets() thread started")
        while self.running:
            try :
                msg = self.outbound_q.get(block=False)
                logger.debug ("sending "+str(msg))
                self.sock.sendall(msg)
                time.sleep(0.001)
            except :
                pass

    def putInOutBoundQueue(self, command):
        self.outbound_q.put(command)    

    def send_command (self,command):
        logger.debug ("Sending command: " + command)
        command += '\n'
        # send command
        self.putInOutBoundQueue(command.encode())
        #self.sock.sendall(command.encode())


