import logging

from concurrence import Tasklet, dispatch, DeferredQueue
from concurrence.io import Socket, BufferedStreamShared, Connector

from xml.parsers import expat

import cPickle as pickle

class XMPPParser(object):
    STATE_INIT = 0
    STATE_STREAM_START = 1

    def __init__(self):
        self.p = expat.ParserCreate('utf-8')
        self.p.buffer_text = True
        self.p.ordered_attributes = True
        self.p.StartElementHandler = self.start_element
        self.p.EndElementHandler = self.end_element
        self.p.CharacterDataHandler = self.char_data
        self.level = 0
        self.state = self.STATE_INIT
        self.b = []

    def start_element(self, name, attrs):
        event = (1, (name, attrs))
        #print 'event', event
        self.b.append(event)
        if self.level == 0:
            assert self.state == self.STATE_INIT
            self.state = self.STATE_STREAM_START
        self.level += 1

    def end_element(self, name):
        #print 'End element:', name
        self.b.append((2, name))
        self.level -= 1

    def char_data(self, data):
        #print 'Character data:', repr(data)
        self.b.append((3, data))

    def parse(self, data):
        self.p.Parse(data, False)


class ApplicationConnection(object):
    def __init__(self, socket):
        self.write_queue = DeferredQueue()
        self.stream = BufferedStreamShared(socket)

    def write_packet(self, headers, data):
        def _write_packet():
            with self.stream.get_writer() as writer:
                for key, value in headers:
                    writer.write_bytes("%s:%s\r\n" % key, value)
                writer.write_bytes("n:%d\r\n" % len(data))
                writer.write_bytes("\r\n")
                writer.write_bytes(data)
                writer.flush()
        self.write_queue.defer(_write_packet)

application_connection = None

class Connection(object):

    def __init__(self, client_socket):
        self.stream = BufferedStreamShared(client_socket)
        self.parser = XMPPParser()

    def _read(self):
        with self.stream.get_reader() as reader:
            while True:
                data = reader.read_bytes_available()
                print '_read', data
                self.parser.parse(data)
                if self.parser.state == XMPPParser.STATE_STREAM_START:
                    print 'wrt packet'
                    application_connection.write_packet({}, pickle.dumps(self.parser.b))
                    print 'wrt_packet done'

    def accept(self):
        print 'accept'
        Tasklet.set_current_timeout(20.0)
        self._read()

def main():
    global application_connection
    application_connection = ApplicationConnection(Connector.connect(('0.0.0.0', 9099)))

    addr = ('0.0.0.0', 5222)
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


