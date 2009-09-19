# Copyright (C) 2009, Hyves (Startphone Ltd.)
#
# This module is part of the Concurrence Framework and is released under
# the New BSD License: http://www.opensource.org/licenses/bsd-license.php

from concurrence import Tasklet, Channel, Message, TaskletError
from concurrence.timer import Timeout
from concurrence.io.socket import Socket
from concurrence.io.buffered import BufferedStream
from concurrence.containers.deque import Deque

import logging
import cPickle as pickle

#TODO:
#proper buffer sizes
#bundling of multiple requests in 1 flush (autoflush on/off)
#statistics
#not use pickle for string and unicode types (use flags to indicate this)
#timeout on commands (for clients, support Timeout.current)
#plugable serialization support (and/or provide choise, default (py-serialized, utf-8 encoded json, etc)?
#todo detect timeouts on write/read, and mark host as dead
#keep some time before retrying host
#global consistent hashing algorithm for accessing set of memcached servers
#replicated set
#multiple connections to same host
#append, prepend commands
#close down node no recv ERROR?
#support for cas command
#UPD support
#binary support

class MemcacheResult(object):
    pass
        
MemcacheResult.STORED = MemcacheResult()
MemcacheResult.NOT_STORED = MemcacheResult()
MemcacheResult.EXISTS = MemcacheResult()
MemcacheResult.NOT_FOUND = MemcacheResult()
MemcacheResult.DELETED = MemcacheResult()
MemcacheResult.ERROR = MemcacheResult()
MemcacheResult.RESPONSES = {"STORED": MemcacheResult.STORED,
                           "NOT_STORED": MemcacheResult.NOT_STORED,
                           "EXISTS": MemcacheResult.EXISTS,
                           "NOT_FOUND": MemcacheResult.NOT_FOUND,
                           "DELETED": MemcacheResult.DELETED}

class MemcacheCommand(object):
    def __init__(self):
        super(MemcacheCommand, self).__init__()
        self.channel = Channel()

class MemcacheCommandGet(MemcacheCommand):
    def __init__(self, keys):
        super(MemcacheCommandGet, self).__init__()
        self.keys = keys
        self.result = {}

    def write(self, writer):
        writer.write_bytes("get")
        for key in self.keys:
            writer.write_bytes(" " + key)

    def read(self, reader):
        result = {}
        while True:
            response_line = reader.read_line()
            if response_line.startswith('VALUE'):
                response_fields = response_line.split(' ')
                key = response_fields[1]
                flags = int(response_fields[2])
                n = int(response_fields[3])
                encoded_value = reader.read_bytes(n)
                reader.read_line() #\r\n
                result[key] = pickle.loads(encoded_value)
            elif response_line == 'END':
                return result 
            else:
                assert False, "protocol error"

class MemcacheCommandWithResult(MemcacheCommand):
    def read(self, reader):
        response_line = reader.read_line()
        result = MemcacheResult.RESPONSES.get(response_line, None)
        assert result is not None, "protocol error"
        return result
    
class MemcacheCommandDelete(MemcacheCommandWithResult):
    def __init__(self, key):
        super(MemcacheCommandDelete, self).__init__()
        self.key = key

    def write(self, writer):
        writer.write_bytes("delete %s" % (self.key, ))

class MemcacheCommandStorage(MemcacheCommandWithResult):
    def __init__(self, key, value, flags):
        super(MemcacheCommandStorage, self).__init__()
        self.key = key
        self.value = value
        self.flags = flags

    def write(self, writer):
        encoded_value = pickle.dumps(self.value, -1)
        writer.write_bytes("%s %s %d 0 %d\r\n" % (self.cmd, self.key, self.flags, len(encoded_value)))
        writer.write_bytes(encoded_value)

class MemcacheCommandSet(MemcacheCommandStorage):
    cmd = "set"

class MemcacheCommandAdd(MemcacheCommandStorage):
    cmd = "add"

class MemcacheCommandReplace(MemcacheCommandStorage):
    cmd = "replace"

class MemcacheConnection(object):
    """this represents the connection/protocol to 1 memcached host
    this class supports concurrent usage of get/set methods by multiple
    tasks, the cmds are queued and performed in order agains the memcached host.    
    """
    log = logging.getLogger('MemcacheConnection')

    STATE_CLOSED = 0
    STATE_CONNECTED = 1
    STATE_FAILED = 2

    class _MSG_COMMAND(Message): pass
    class _MSG_RESPONSE(Message): pass

    def __init__(self, addr):
        self._addr = addr
        self._stream = None
        self._state = self.STATE_CLOSED
        self._command_writer_task = Tasklet.new(self._command_writer)()
        self._response_reader_task = Tasklet.new(self._response_reader)()

    def _reconnect(self):
        if self._state == self.STATE_CONNECTED:
            return
        else:
            assert self._stream is None
            #TODO exception/timeout
            self._stream = BufferedStream(Socket.connect(self._addr, -1))
            self._state = self.STATE_CONNECTED

    def close(self):
        self._fail()
        self._command_writer_task.kill()
        self._response_reader_task.kill()
        self._command_writer_task = None
        self._response_reader_task = None

    @property
    def reader(self):
        return self._stream.reader

    @property
    def writer(self):
        return self._stream.writer

    def _fail(self):
        pass
#        #raise exception on all waiting tasks still in the queues
#        for cmd in self._command_queue:
#            cmd.channel.send_exception(TaskletError, e, Tasklet.current())
#        for cmd in self._response_queue:
#            cmd.channel.send_exception(TaskletError, e, Tasklet.current())
#        self._stream.close()
#        self._stream = None

    def _response_reader(self):
        for msg, (cmd,), _ in Tasklet.receive():
            try:
                cmd.channel.send(cmd.read(self.reader))
            except Exception, e:
                self.log.exception('error while reading response')
                self._fail()
            
    def _command_writer(self):
        for msg, (cmd,), _ in Tasklet.receive():
            try:
                self._reconnect()
                self.writer.clear()
                cmd.write(self.writer)
                self.writer.write_bytes('\r\n')
                self.writer.flush()
                self._MSG_RESPONSE.send(self._response_reader_task)(cmd)
            except Exception:
                self.log.exception('error while writing command')
                self._fail()

    def _do_command(self, cmd):
        if self._state == self.STATE_FAILED:
            return MemcacheResult.ERROR
            
        self._MSG_COMMAND.send(self._command_writer_task)(cmd)

        try:
            return cmd.channel.receive()
        except Exception:
            return MemcacheResult.ERROR

    def set(self, key, data, flags = 0):
        return self._do_command(MemcacheCommandSet(key, data, flags))

    def add(self, key, data, flags = 0):
        return self._do_command(MemcacheCommandAdd(key, data, flags))

    def replace(self, key, data, flags = 0):
        return self._do_command(MemcacheCommandReplace(key, data, flags))

    def delete(self, key):
        return self._do_command(MemcacheCommandDelete(key))

    def get(self, key):
        result = self._do_command(MemcacheCommandGet([key]))
        if key in result:
            return result[key]
        else:
            return None

    def multi_get(self, keys):
        return self._do_command(MemcacheCommandGet(keys))

            

