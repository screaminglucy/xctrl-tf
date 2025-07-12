import sys
import socket
import time
import logging

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

def fader_db_to_value (db):
    value = db * 100
    print (str(value))
    return str(value)
   # Max Fader Value: 1000
   #Min Fader Value: -13800
   #Negative Infinity Value: -32768

def fader_value_to_db (value):
    db = value / 100
    return db

# Host is console's IP
host ="192.168.10.5"
# Port must be 49280
port =49280

def wait_for_server(host, port, timeout=6000, retry_interval=1):
    """
    Attempts to connect to a server at the given host and port,
    retrying until successful or a timeout is reached.
    """
    start_time = time.time()
    while time.time() - start_time < timeout:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            # Attempt to connect non-blocking
            result = s.connect_ex((host, port))
            if result == 0:  # Connection successful
                logger.info(f"Successfully connected to {host}:{port}")
                return s  # Return the connected socket
            else:
                logger.info(f"Connection failed (Error: {errno.errorcode[result]}). Retrying...")
                s.close()  # Close the socket before retrying
        except Exception as e:
            logger.info(f"An error occurred: {e}. Retrying...")
            s.close()
        time.sleep(retry_interval)
    logger.info(f"Timed out after {timeout} seconds. Could not connect to {host}:{port}")
    return None

def send_command (command):
    command += '\n'
    # connect socket
    connected_socket = wait_for_server(host, port)

    # send command
    connected_socket.sendall(command.encode())

    # receive a message before closing socket
    connected_socket.recv(1500)

    # close socket
    connected_socket.close ()


