import socketserver
import socket


class Handler(socketserver.BaseRequestHandler):
    def handle(self):
        while True:   # loop indefinitely and serve multiple clients
            cmd = self.request.recv(1024).decode()  # receive the command from client
            if not cmd: break

            self.request.sendall(cmd.encode())   # echo back what was received

def find_available_port():
    # Create a TCP/IP socket and connect it to the port you want to check.
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1)  # Set a timeout so we don't block indefinitely.

    for port in range(1024, 65536):  # A common range of unused ports is between 1024 and 65535
        if not sock.connect_ex(('localhost', port)):
            return port

    return None

HOST, PORT = 'localhost', find_available_port()
Handler = socketserver.TCPServer((HOST, PORT), Handler)
print('Server running on port {}...'.format(PORT))
Handler.serve_forever()