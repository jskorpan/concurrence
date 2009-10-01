# Copyright (C) 2009, Hyves (Startphone Ltd.)
#
# This module is part of the Concurrence Framework and is released under
# the New BSD License: http://www.opensource.org/licenses/bsd-license.php

from concurrence import Tasklet, Channel, Message, TaskletPool, Lock, TaskletError
from concurrence.timer import Timeout
from concurrence.io import Socket, Buffer
from concurrence.io.buffered import BufferedStream, BufferedReader, BufferedWriter
from concurrence.containers.deque import Deque

from concurrence.memcache import ketama

import logging
import cPickle as pickle

#TODO:
#proper buffer sizes
#bundling of multiple requests in 1 flush (autoflush on/off)
#statistics
#not use pickle for string and unicode types (use flags to indicate this)
#gzip support
#timeout on commands (test tasklet based timeout)
#plugable serialization support (and/or provide choise, default (py-serialized, utf-8 encoded json, etc)?
#todo detect timeouts on write/read, and mark host as dead
#keep some time before retrying host
#global consistent hashing algorithm for accessing set of memcached servers
#replicated set
#multiple connections to same host (with maximum)
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

class Codec(object):
    def decode(self, flags, encoded_value):
        assert False, "implement"

    def encode(self, value):
        assert False, "implement"

class DefaultCodec(Codec):
    def decode(self, flags, encoded_value):
        return pickle.loads(encoded_value)

    def encode(self, value):
        return pickle.dumps(value, -1), 0

class RawCodec(Codec):
    def decode(self, flags, encoded_value):
        return encoded_value

    def encode(self, value):
        return str(value), 0
            
class _MemcacheCmd(object):
    pass

class _MemcacheCmdGet(_MemcacheCmd):
    def __init__(self, keys):
        self.keys = keys
        self.result = {}

    def write(self, writer):
        writer.write_bytes("get %s\r\n" % " ".join(self.keys))

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
                result[key] = self.codec.decode(flags, encoded_value)
            elif response_line == 'END':
                return result 
            else:
                assert False, "protocol error"

class _MemcacheCmdWithResult(_MemcacheCmd):
    def read(self, reader):
        response_line = reader.read_line()
        result = MemcacheResult.RESPONSES.get(response_line, None)
        assert result is not None, "protocol error"
        return result
    
class _MemcacheCmdDelete(_MemcacheCmdWithResult):
    def __init__(self, key):
        self.key = key

    def write(self, writer):
        writer.write_bytes("delete %s\r\n" % (self.key, ))

class _MemcacheCmdStorage(_MemcacheCmdWithResult):
    def __init__(self, key, value):
        self.key = key
        self.value = value
        
    def write(self, writer):
        encoded_value, flags = self.codec.encode(self.value)
        writer.write_bytes("%s %s %d 0 %d\r\n%s\r\n" % (self.cmd, self.key, flags, len(encoded_value), encoded_value))

class _MemcacheCmdSet(_MemcacheCmdStorage):
    cmd = "set"

class _MemcacheCmdAdd(_MemcacheCmdStorage):
    cmd = "add"

class _MemcacheCmdReplace(_MemcacheCmdStorage):
    cmd = "replace"


class _MemcacheTCPConnection(object):
    def __init__(self):
        self.read_lock = Lock()
        self.write_lock = Lock()

    def connect(self, addr):
        self._socket = Socket.connect(addr, -2)

class _MemcacheTCPConnectionManager(object):
    def __init__(self):
        self._connections = {} #addr -> conn 
 
    def get_connection(self, addr):
        if not addr in self._connections:
            connection = _MemcacheTCPConnection()
            connection.connect(addr)
            self._connections[addr] = connection 
        return self._connections[addr]

class _MemcacheWorkerTasklet(Tasklet):

    def __init__(self):
        super(_MemcacheWorkerTasklet, self).__init__()
        self.reader = BufferedReader(None, Buffer(1024))    
        self.writer = BufferedWriter(None, Buffer(1024))

    def set_context(self, timeout, connection):
        self.timeout = timeout
        self.reader.stream = connection._socket
        self.writer.stream = connection._socket

class MemcacheModuloBehaviour(object):
    def __init__(self):
        pass

    def set_servers(self, servers):
        self._servers = servers

    def key_to_addr(self, key):
        return self._servers[hash(key) % len(self._servers)]

class MemcacheKetamaBehaviour(object):
    def __init__(self):
        self._continuum = None

    def set_servers(self, servers):
        self._continuum = ketama.build_continuum(servers)

    def key_to_addr(self, key):
        return ketama.get_server(key, self._continuum)

class Memcache(object):
    def __init__(self, servers = None):
        self.read_timeout = 10
        self.write_timeout = 10
        self.connect_timeout = 2

        tp = TaskletPool(4, _MemcacheWorkerTasklet) #TODO make overridable singleton
        self._defer = tp.defer
        self._connection_manager = _MemcacheTCPConnectionManager() #TODO make overridable singleton

        self.set_codec(DefaultCodec())
        self.set_behaviour(MemcacheKetamaBehaviour()) #default
        
        if servers is not None:
            self.set_servers(servers)

    def set_codec(self, codec):
        self._codec = codec
        
    def set_behaviour(self, behaviour):
        self._behaviour = behaviour
        self._key_to_addr = behaviour.key_to_addr

    def set_servers(self, servers):
        self._behaviour.set_servers(servers)

    def _read_result(self, connection, cmd, result_channel):
        current_task = Tasklet.current()
        current_task.set_context(self.read_timeout, connection)
        cmd.codec = self._codec
        reader = current_task.reader
        with connection.read_lock:
            result = cmd.read(reader)
        result_channel.send(result)

    def _write_command(self, connection, cmd, result_channel):
        current_task = Tasklet.current()
        current_task.set_context(self.write_timeout, connection)
        cmd.codec = self._codec
        writer = current_task.writer
        with connection.write_lock:
            cmd.write(writer)
            writer.flush()
            self._defer(self._read_result, connection, cmd, result_channel)

    def _connect_by_addr(self, addr, keys, result_channel):
        current_task = Tasklet.current()
        current_task.timeout = self.connect_timeout
        connection = self._connection_manager.get_connection(addr)
        result_channel.send((connection, keys))

    def _connect_by_key(self, key):
        return self._connection_manager.get_connection(self._key_to_addr(key))

    def _keys_to_addr(self, keys):
        addrs = {} #addr->[keys]
        for key in keys:
            addr = self._key_to_addr(key)
            if addr in addrs:   
                addrs[addr].append(key)
            else:
                addrs[addr] = [key]
        return addrs

    def delete(self, key):
        cmd = _MemcacheCmdDelete(key)
        result_channel = Channel()
        self._defer(self._write_command, self._connect_by_key(key), cmd, result_channel)
        return result_channel.receive()
        
    def set(self, key, data):
        cmd = _MemcacheCmdSet(key, data)
        result_channel = Channel()
        self._defer(self._write_command, self._connect_by_key(key), cmd, result_channel)
        return result_channel.receive()

    def add(self, key, data):
        cmd = _MemcacheCmdAdd(key, data)
        result_channel = Channel()
        self._defer(self._write_command, self._connect_by_key(key), cmd, result_channel)
        return result_channel.receive()

    def replace(self, key, data):
        cmd = _MemcacheCmdReplace(key, data)
        result_channel = Channel()
        self._defer(self._write_command, self._connect_by_key(key), cmd, result_channel)
        return result_channel.receive()

    def get(self, key):
        cmd = _MemcacheCmdGet([key])
        result_channel = Channel()
        self._defer(self._write_command, self._connect_by_key(key), cmd, result_channel)
        result = result_channel.receive()
        return result.get(key, None)

    def get_multi(self, keys):
        result_channel = Channel()
        grouped = self._keys_to_addr(keys).items()
        n = len(grouped)
        for addr, _keys in grouped:
            self._defer(self._connect_by_addr, addr, _keys, result_channel)
        for connection, _keys in result_channel.receive_n(n):
            self._defer(self._write_command, connection, _MemcacheCmdGet(_keys), result_channel)
        result = {}        
        for _result in result_channel.receive_n(n):
            result.update(_result)
        return result

 
                    




            

