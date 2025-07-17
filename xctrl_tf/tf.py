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
        logger.info (data_list)
        ip = addr[0]
        if ip!=get_ip():
            logger.info (ip)
            logger.info ('detected yamaha')
            detect = True
    return ip
        

class tf_rcp:

    def __init__(self, ip=None):
        if ip is None:
            ip = detect_yamaha()
        self.host = ip
        self.outbound_q = queue.Queue()
        self._active = False
        self.lastMsgTime = None
        self.onMixMeterRcv = None
        self.onChMeterRcv = None
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
                cmd = 'mtrstart MIXER:Current/InCh/PreHPF 200' #time interval
                self.send_command(cmd)
                cmd = 'mtrstart MIXER:Current/Mix/PreEQ 200' #time interval
                self.send_command(cmd)
            threading.Timer(10, self.Metering).start()
    
    def setOnChMeterRcv(self, callback):
        self.onChMeterRcv = callback

    def setOnMixMeterRcv(self, callback):
        self.onMixMeterRcv = callback

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
                            else:
                                logger.debug(f"Received: {message.decode()}")
                        #end of message received
                        buffer = buffer[index_of_char:]

    def processOutgoingPackets (self):
        logger.info ("tf processOutgoingPackets() thread started")
        while self.running:
            try :
                msg = self.outbound_q.get(block=False)
                logger.debug ("sending "+str(msg))
                self.sock.sendall(msg)
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


