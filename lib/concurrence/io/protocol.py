from concurrence import Tasklet, DeferredQueue
from concurrence.io import BufferedStreamShared

class Protocol(object):
    __slots__ = ['_stream', '_write_queue']

    def __init__(self, stream):
        self._stream = BufferedStreamShared(stream)
        self._write_queue = DeferredQueue()
        self._notify_readable()

    def _notify_readable(self):
        self._stream._stream.readable.notify(self._on_readable)

    def _on_readable(self, timedout):
        if timedout:
            Tasklet.defer(self.read_timeout)
        else:
            Tasklet.defer(self._read)

    def _read(self):
        with self._stream.get_reader() as reader:
            self.read(reader)
        self._notify_readable()

    def read(self, reader):
        pass

    def read_timeout(self):
        pass

    def write(self, f):
        def _f():
            with self._stream.get_writer() as writer:
                f(writer)
        self._write_queue.defer(_f)

    def write_timeout(self):
        pass
