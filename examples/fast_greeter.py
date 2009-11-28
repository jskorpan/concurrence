from concurrence import dispatch, Tasklet
from concurrence.io import BufferedStream, Socket

class Connection(object):
    def __init__(self, stream):
        self.stream = BufferedStream(stream, 1024)
        
    def handle(self):
        """writes the familiar greeting to client"""
        with self.stream.get_writer() as writer:
            writer.write_bytes("HTTP/1.0 200 OK\r\n")
            writer.write_bytes("Content-Length: 12\r\n")    
            writer.write_bytes("\r\n")
            writer.write_bytes("Hello World!")
            writer.flush()
        self.stream.close()
       
def server():
    """accepts connections on a socket, and dispatches
    new tasks for handling the incoming requests"""
    server_socket = Socket.server(('localhost', 8080))
    while True:
        client_socket = server_socket.accept()
        client_connection = Connection(client_socket)
        Tasklet.defer(client_connection.handle)

if __name__ == '__main__':
    import logging
    logging.basicConfig()
    dispatch(server)
