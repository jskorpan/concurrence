from concurrence import dispatch, Tasklet
from concurrence.io import BufferedStream, Socket

def handle(client_socket):
    stream = BufferedStream(client_socket)
    with stream.get_writer() as writer:
        writer.write_bytes("HTTP/1.0 200 OK\r\n")
        writer.write_bytes("Content-Length: 12\r\n")
        writer.write_bytes("\r\n")
        writer.write_bytes("Hello World!")
        writer.flush()
    stream.close()

def server():
    """accepts connections on a socket, and dispatches
    new tasks for handling the incoming requests"""
    server_socket = Socket.server(('localhost', 8080))
    for client_socket in server_socket.accept_iter():
        Tasklet.defer(handle, client_socket)

if __name__ == '__main__':
    import logging
    logging.basicConfig()
    dispatch(server)
