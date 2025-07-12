import sys
import socket
import time
import logging
import threading
import _thread

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

class tf_rcp:

    def __init__(self, ip):
        self.host = ip
        self._active = False
        self.lastMsgTime = None
        self.connect()

    def connect(self):
        self.sock = None
        self.port = 49280
        _thread.start_new_thread(self.maintain_connection, ())
        _thread.start_new_thread(self.HandleMsg, ())
        self.running = True
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

    def HandleMsg (self):
        # receive a message 
        while self.running:
            if self._active:
                data = self.sock.recv(1500)
                if data:
                    logger.info(f"Received: {data.decode()}")

    def send_command (self,command):
        logger.info ("Sending command: " + command)
        command += '\n'
        
        # send command
        self.sock.sendall(command.encode())

tf = tf_rcp('192.168.10.5')
