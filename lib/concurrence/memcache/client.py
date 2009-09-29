# Copyright (C) 2009, Hyves (Startphone Ltd.)
#
# This module is part of the Concurrence Framework and is released under
# the New BSD License: http://www.opensource.org/licenses/bsd-license.php

from concurrence import Tasklet, Channel, Message, TaskletPool, Lock, TaskletError
from concurrence.timer import Timeout
from concurrence.io import Socket, Buffer
from concurrence.io.buffered import BufferedStream, BufferedReader, BufferedWriter
from concurrence.containers.deque import Deque

import logging
import cPickle as pickle

#TODO:
#proper buffer sizes
#bundling of multiple requests in 1 flush (autoflush on/off)
#statistics
#not use pickle for string and unicode types (use flags to indicate this)
#timeout on commands (test tasklet based timeout)
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
    pass

class MemcacheCommandGet(MemcacheCommand):
    def __init__(self, keys):
        self.keys = keys
        self.result = {}

    def write(self, writer):
        writer.write_bytes("get")
        for key in self.keys:
            writer.write_bytes(" " + key)
        writer.write_bytes('\r\n')

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
        self.key = key

    def write(self, writer):
        writer.write_bytes("delete %s\r\n" % (self.key, ))

class MemcacheCommandStorage(MemcacheCommandWithResult):
    def __init__(self, key, value, flags):
        encoded_value = pickle.dumps(value, -1)
        self.cmd_bytes = "%s %s %d 0 %d\r\n%s\r\n" % (self.cmd, key, flags, len(encoded_value), encoded_value)

    def write(self, writer):
        writer.write_bytes(self.cmd_bytes)

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
        self._stream = BufferedStream(Socket.connect(addr, -2))

    def close(self):
        self._stream.close()
        self._stream = None

    def _do_command(self, cmd):
        try:
            writer = self._stream.writer
            cmd.write(writer)
            writer.flush()
            reader = self._stream.reader
            return cmd.read(reader)
        except Exception:
            self.log.exception("error while performing command")
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

class PooledMemcacheConnection(object):
    def __init__(self):
        self.read_lock = Lock()
        self.write_lock = Lock()

    def connect(self, addr):
        self._socket = Socket.connect(addr, -1)
        
class MemcacheWorkerTasklet(Tasklet):

    def __init__(self):
        super(MemcacheWorkerTasklet, self).__init__()
        self.reader = BufferedReader(None, Buffer(1024))    
        self.writer = BufferedWriter(None, Buffer(1024))

    def set_context(self, timeout, connection):
        self.timeout = timeout
        self.reader.stream = connection._socket
        self.writer.stream = connection._socket

class Memcache(object):
    def __init__(self):
        self.read_timeout = 10
        self.write_timeout = 10

        tp = TaskletPool(5, MemcacheWorkerTasklet)
        self._defer = tp.defer
        self._servers = {} #addr->conn
        self._server = None

    def set_servers(self, server_list):
        for addr in server_list:
            conn = PooledMemcacheConnection()
            conn.connect(addr)
            self._servers[addr] = conn
            self._server = conn

    def _read_result(self, connection, cmd, result_channel):
        current_task = Tasklet.current()
        current_task.set_context(self.read_timeout, connection)
        reader = current_task.reader
        with connection.read_lock:
            result = cmd.read(reader)
        result_channel.send(result)

    def _write_command(self, connection, cmd, result_channel):
        current_task = Tasklet.current()
        current_task.set_context(self.write_timeout, connection)
        writer = current_task.writer
        with connection.write_lock:
            cmd.write(writer)
            writer.flush()
            self._defer(self._read_result, connection, cmd, result_channel)

    def _server_by_key(self, key):
        return self._server

    def set(self, key, data, flags = 0):
        cmd = MemcacheCommandSet(key, data, flags)
        result_channel = Channel()
        self._defer(self._write_command, self._server_by_key(key), cmd, result_channel)
        return result_channel.receive()
        

            

