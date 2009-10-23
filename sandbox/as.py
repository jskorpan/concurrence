import logging

from concurrence import Tasklet, dispatch
from concurrence.io import Socket, BufferedStreamShared

from xml.parsers import expat

import cPickle as pickle

class Connection(object):

    def __init__(self, client_socket):
        self.stream = BufferedStreamShared(client_socket)

    def accept(self):
        print 'accept cm'
        Tasklet.set_current_timeout(20.0)
        with self.stream.get_reader() as reader:
            headers = {}
            while True:
                line = reader.read_line()
                if line == '': break
                key, value = line.split(':')
                headers[key] = value
            assert 'n' in headers
            n = int(headers['n'])
            data = reader.read_bytes(n)
            print pickle.loads(data)

def main():

    addr = ('0.0.0.0', 9099)
    server_socket = Socket.from_address(addr)
    server_socket.set_reuse_address(True)
    server_socket.bind(addr)
    server_socket.listen(512)

    while True:
        client_socket = server_socket.accept()
        connection = Connection(client_socket)
        Tasklet.defer(connection.accept)

if __name__ == '__main__':
    logging.basicConfig()
    dispatch(main)


