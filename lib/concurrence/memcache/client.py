# Copyright (C) 2009, Hyves (Startphone Ltd.)
#
# This module is part of the Concurrence Framework and is released under
# the New BSD License: http://www.opensource.org/licenses/bsd-license.php

from concurrence import Tasklet, Channel, TaskletError
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

class MemcacheError(Exception):
    pass

class MemcacheResult(object):
    pass
        
MemcacheResult.STORED = MemcacheResult()
MemcacheResult.NOT_STORED = MemcacheResult()
MemcacheResult.EXISTS = MemcacheResult()
MemcacheResult.NOT_FOUND = MemcacheResult()
MemcacheResult.DELETED = MemcacheResult()

MemcacheResult.ALL = {"STORED": MemcacheResult.STORED,
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
        #print response_line
        result = MemcacheResult.ALL.get(response_line, None)
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

    def __init__(self):
        self._stream = None

    def connect(self, addr):
        assert self._stream is None, "already connected"
        self._stream = BufferedStream(Socket.connect(addr, Timeout.current()))
        self._command_queue = Deque()
        self._response_queue = Deque()
        self._command_writer_task = Tasklet.new(self._command_writer)()
        self._response_reader_task = Tasklet.new(self._response_reader)()

    def close(self):
        self._response_reader_task.kill()
        self._command_writer_task.kill()
        self._response_reader_task = None
        self._command_writer_task = None
        #raise exception on all waiting tasks still in the queues
        for cmd in self._command_queue:
            cmd.channel.send_exception(TaskletError, e, Tasklet.current())
        for cmd in self._response_queue:
            cmd.channel.send_exception(TaskletError, e, Tasklet.current())
        self._command_queue = None
        self._response_queue = None
        self._stream.close()
        self._stream = None

    def _read_response(self, reader):
        cmd = self._response_queue.popleft(True)
        try:
            result = cmd.read(reader)
            cmd.channel.send(result)
        except Exception, e:
            cmd.channel.send_exception(TaskletError, e, Tasklet.current())
            raise 

    def _write_command(self, writer):
        try:
            cmd = self._command_queue.popleft(True)
            writer.clear()
            cmd.write(writer)
            writer.write_bytes('\r\n')
            writer.flush()
            self._response_queue.append(cmd)
        except Exception, e:
            cmd.channel.send_exception(TaskletError, e, Tasklet.current())
            raise

    def _response_reader(self):
        reader = self._stream.reader
        while True:
            try:
                self._read_response(reader)
            except Exception, e:
                self.close()
                self.log.exception('error while reading response')
                return #this ends reader
            
    def _command_writer(self):
        writer = self._stream.writer       
        while True:
            try:
                self._write_command(writer)
            except Exception, e:
                self.close()
                self.log.exception('error while writing command')
                return #this ends writer

    def _do_command(self, cmd):
        self._command_queue.append(cmd)
        try:
            return cmd.channel.receive()
        except TaskletError, e:
            raise MemcacheError(str(e.cause))

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

            

