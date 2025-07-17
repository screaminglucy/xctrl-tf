import sys
import socket
import time
import logging
import threading
import _thread
from tfmeter import meter_dict
import queue

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

def fader_db_to_value (db):
    value = int(db * 100)
    logger.info ("fader_db_to_value "+str(value))
    return str(value)
   # Max Fader Value: 1000
   #Min Fader Value: -13800
   #Negative Infinity Value: -32768

def fader_value_to_db (value):
    db = value / 100
    return db


def get_ip():
  """Retrieves the local IP address of the machine."""
  hostname = socket.gethostname()
  local_ip = socket.gethostbyname(hostname)
  return local_ip

def detect_yamaha (): 
    #send udp broadcast to probe for mixer
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) 
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) 
    ip = get_ip()
    logger.info ('my ip is '+ip)
    ip_bytes = socket.inet_aton(ip)
    message5 = b"YSDP\x00D\x00\x04"
    message5 += ip_bytes
    message5 += b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x18\xc0"
    message5 += b"M1\xc9\x20\x08"
    message5 += b"_ypax-tf\x00!\x12Yamaha Corporation\x03TF5\x09Yamaha TF"

    message = b"YSDP\x00H\x00\x04"
    message += ip_bytes
    message += b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x18\xc0"
    message += b"M1\xc9\x20\x08"
    message += b"_ypax-tf\x00%\x12Yamaha Corporation\x07TF-RACK\x09Yamaha TF"
    sock.bind(('', 54330))
    b = (ip.split('.'))[:-1]
    b.append('255')
    b = '.'.join(b)
    logger.info ('broadcast to ' + b)
    sock.sendto(message, (b, 54330))
    sock.sendto(message5, (b, 54330))
    detect = False
    while detect == False:
        data, addr = sock.recvfrom(1024) # buffer size is 1024 bytes
        logger.info("received message: %s" % data)
        data_list = list(data)
        logger.debug (data_list)
        ip = addr[0]
        if ip!=get_ip():
            logger.info (ip)
            logger.info ('detected yamaha')
            detect = True
    return ip
        

class tf_rcp:

    def __init__(self, ip=None):
        self.mix = 9 #aux9
        if ip is None:
            ip = detect_yamaha()
        self.host = ip
        self.outbound_q = queue.Queue()
        self._active = False
        self.last_fader_updates = [time.time()]*40
        self.lastMsgTime = None
        self.onMixMeterRcv = None
        self.onChMeterRcv = None
        self.onFaderNameRcv = None
        self.onFaderColorRcv = None
        self.onFaderValueRcv = None
        self.onChannelMute = None
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
        start_time = time.time()
        retry_interval = 1
        timeout = 6000
        while self.running:
            while time.time() - start_time < timeout:
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
                        return # Return the connected socket
                    else:
                        logger.info(f"Connection failed (Error: {errno.errorcode[result]}). Retrying...")
                        s.close()  # Close the socket before retrying
                except Exception as e:
                    logger.info(f"An error occurred: {e}. Retrying...")
                    s.close()
                time.sleep(retry_interval)
            logger.info(f"Timed out after {timeout} seconds. Could not connect to {self.host}:{self.port}")
            while self.running and self._active:
                time.sleep(5)
        self.sock.close()

    def SendKeepAlive(self, timeout=30):
        if self.running:
            if self._active:
                self.send_command("devstatus runmode")
            threading.Timer(1, self.SendKeepAlive).start()
            if self.lastMsgTime is not None:
                if (time.time() - self.lastMsgTime) > timeout:
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

    def getFaderName (self, channel):
        cmd = 'get MIXER:Current/InCh/Label/Name ' + str(channel)+' 0' 
        self.send_command(cmd)
        logger.debug ('sent '+cmd)

    def getFaderColor(self,channel):
        cmd = 'get MIXER:Current/InCh/Label/Color ' + str(channel)+' 0' 
        self.send_command(cmd)
        logger.debug ('sent '+cmd)

    def getChannelOn(self,channel):
        if self.mix == 0:
            cmd = 'get MIXER:Current/InCh/Fader/On ' + str(channel)+' 0 1' 
        else:
            cmd = 'get MIXER:Current/InCh/ToMix/On ' + str(channel)+' '+str(self.mix)+' 1'
        self.send_command(cmd)
        logger.debug ('sent '+cmd)

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

    def sendFaderValue(self,chan, db):
        if self.mix == 0:
            cmd = 'set MIXER:Current/InCh/Fader/Level '+str(chan)+' 0 '+fader_db_to_value(db) 
        else: 
            cmd = 'set MIXER:Current/InCh/ToMix/Level '+str(chan)+' '+str(self.mix)+' '+fader_db_to_value(db)
        if (time.time() - self.last_fader_updates[chan]) > 0.100:
            self.send_command(cmd)
            self.last_fader_updates[chan] = time.time() 

    def HandleMsg (self):
        # receive a message 
        while self.running:
            buffer = b""
            if self._active:
                data = self.sock.recv(1500)
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
                            elif ((messageString.startswith('OK get MIXER:Current/InCh/Fader/On') or messageString.startswith('NOTIFY set MIXER:Current/InCh/Fader/On')) and self.mix == 0) or \
                                  ((messageString.startswith('OK get MIXER:Current/InCh/ToMix/On') or messageString.startswith('NOTIFY set MIXER:Current/InCh/ToMix/On')) and self.mix != 0):
                                logger.info(messageString)
                                chan = int(messageString.split(' ')[3])
                                value = int(messageString.split(' ')[5])
                                if value == 0:
                                    value = False
                                else:
                                    value = True
                                if self.onChannelMute:
                                    self.onChannelMute(chan,value)
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


