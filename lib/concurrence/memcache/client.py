# Copyright (C) 2009, Hyves (Startphone Ltd.)
#
# This module is part of the Concurrence Framework and is released under
# the New BSD License: http://www.opensource.org/licenses/bsd-license.php

from concurrence import Tasklet, Channel, Message, TaskletPool, Lock, TaskletError, defer
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
#replicated set
#multiple connections to same host (with maximum)
#append, prepend commands
#close down node no recv ERROR?
#support for cas command
#UPD support
#binary support
#how to handle timouts in the pipelined case?
#TODO validate keys!, they are 'txt' not random bins!, e.g. some chars not allowed, which ones?

#!! reverse the locking, e.g. don't let random worker task get locked when we already know it will loc
#instead defer working when we know it can proceed...

#TODO what is the best pattern for enums in python?
class MemcacheResult(object):
    _all = {}

    def __init__(self, name):
        self._name = name
        self._all[name] = self
    
    def __repr__(self):
        return "<MemcacheResult: %s>" % self._name
        
    @classmethod
    def get(cls, name, default):
        return cls._all.get(name, default)

MemcacheResult.STORED = MemcacheResult("STORED")
MemcacheResult.NOT_STORED = MemcacheResult("NOT_STORED")
MemcacheResult.EXISTS = MemcacheResult("EXISTS")
MemcacheResult.NOT_FOUND = MemcacheResult("NOT_FOUND")
MemcacheResult.DELETED = MemcacheResult("DELETED")
MemcacheResult.ERROR = MemcacheResult("ERROR")

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
            
class MemcacheTextProtocol(object):
    def __init__(self, codec = None):
        self._codec = codec

    def _read_result(self, reader):
        response_line = reader.read_line()
        result = MemcacheResult.get(response_line, None)
        assert result is not None, "protocol error"
        return result

    def _write_storage(self, writer, cmd, key, value):
        encoded_value, flags = self._codec.encode(value)
        writer.write_bytes("%s %s %d 0 %d\r\n%s\r\n" % (cmd, key, flags, len(encoded_value), encoded_value))

    def write_get(self, writer, keys):
        writer.write_bytes("get %s\r\n" % " ".join(keys))

    def read_get(self, reader):
        #print 'read_get'
        result = {}
        while True:
            #print 'wait line'
            response_line = reader.read_line()
            #print 'got line', response_line
            if response_line.startswith('VALUE'):
                response_fields = response_line.split(' ')
                key = response_fields[1]
                flags = int(response_fields[2])
                n = int(response_fields[3])
                encoded_value = reader.read_bytes(n)
                reader.read_line() #\r\n
                result[key] = self._codec.decode(flags, encoded_value)
            elif response_line == 'END':
                return result 
            else:
                assert False, "protocol error"
    
    def write_delete(self, writer, key):
        writer.write_bytes("delete %s\r\n" % (key, ))
    
    def read_delete(self, reader):
        return self._read_result(reader)

    def write_set(self, writer, key, value):
        return self._write_storage(writer, "set", key, value)

    def read_set(self, reader):
        return self._read_result(reader)

    def write_add(self, writer, key, value):
        return self._write_storage(writer, "add", key, value)

    def read_add(self, reader):
        return self._read_result(reader)

    def write_replace(self, writer, key, value):
        return self._write_storage(writer, "replace", key, value)

    def read_replace(self, reader):
        return self._read_result(reader)


class _MemcacheTCPConnection(object):
    _write_buffer_size = 1024 * 2
    _read_buffer_size = 1024 * 16

    _reader_pool = []
    _writer_pool = []

    def __init__(self):
        self.read_lock = Lock()
        self.write_lock = Lock()
        self._socket = None
        self._writer = None
        self._reader = None

    def connect(self, addr):
        self._socket = Socket.connect(addr, -2)

    class _borrowed_writer(object):
        def __init__(self, connection):
            if connection._writer is None:
                if connection._writer_pool:
                    writer = connection._writer_pool.pop()
                else:
                    writer = BufferedWriter(None, Buffer(connection._write_buffer_size))
            else:
                writer = connection._writer
            writer.stream = connection._socket
            self._writer = writer
            self._connection = connection

        def __enter__(self):
            return self._writer

        def __exit__(self, type, value, traceback):
            assert self._writer.buffer.position == 0, "todo implement this case?"
            self._connection._writer_pool.append(self._writer)

    class _borrowed_reader(object):
        def __init__(self, connection):
            if connection._reader is None:
                if connection._reader_pool:
                    reader = connection._reader_pool.pop()
                else:
                    reader = BufferedReader(None, Buffer(connection._read_buffer_size))
            else:
                reader = connection._reader
            reader.stream = connection._socket
            self._reader = reader
            self._connection = connection

        def __enter__(self):
            return self._reader

        def __exit__(self, type, value, traceback):
            if self._reader.buffer.remaining:
                self._connection._reader = self._reader
            else:
                self._connection._reader_pool.append(self._reader)
                self._connection._reader = None

    def get_writer(self):
        return self._borrowed_writer(self)

    def get_reader(self):
        return self._borrowed_reader(self)
    
class _MemcacheTCPConnectionManager(object):
    def __init__(self):
        self._connections = {} #addr -> conn 
 
    def get_connection(self, addr):
        if not addr in self._connections:
            connection = _MemcacheTCPConnection()
            connection.connect(addr)
            connection.addr = addr
            self._connections[addr] = connection 
        return self._connections[addr]

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

        self._connection_manager = _MemcacheTCPConnectionManager() #TODO make overridable singleton
        self._protocol = MemcacheTextProtocol()

        self.set_codec(DefaultCodec())
        self.set_behaviour(MemcacheKetamaBehaviour()) #default
        
        if servers is not None:
            self.set_servers(servers)

    def set_codec(self, codec):
        self._codec = codec
        self._protocol._codec = codec

    def set_behaviour(self, behaviour):
        self._behaviour = behaviour
        self._key_to_addr = behaviour.key_to_addr

    def set_servers(self, servers):
        self._behaviour.set_servers(servers)

    def _read_result(self, connection, cmd, result_channel):
        current_task = Tasklet.current()
        current_task.timeout = self.read_timeout
        with connection.read_lock:
            with connection.get_reader() as reader:
                result = getattr(self._protocol, 'read_' + cmd)(reader)
        result_channel.send(result)
        
    def _write_command(self, connection, cmd, args, result_channel):
        #TODO make sure that there is a maximu on the number of writes before
        #we read again, e.g. due to deferred, the corresponding read result 
        #could be postponed indefinitly...
        current_task = Tasklet.current()
        current_task.timeout = self.write_timeout
        with connection.write_lock:
            with connection.get_writer() as writer:
                getattr(self._protocol, 'write_' + cmd)(writer, *args)
                writer.flush()
                defer(self._read_result, connection, cmd, result_channel)
        
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

    def _do_command(self, cmd, *args):
        result_channel = Channel()
        defer(self._write_command, self._connect_by_key(args[0]), cmd, args, result_channel)
        return result_channel.receive()

    def delete(self, key):
        return self._do_command("delete", key)
        
    def set(self, key, data):
        return self._do_command("set", key, data)

    def add(self, key, data):
        return self._do_command("add", key, data)

    def replace(self, key, data):
        return self._do_command("replace", key, data)

    def get(self, key):
        result_channel = Channel()
        defer(self._write_command, self._connect_by_key(key), "get", [[key]], result_channel)
        result = result_channel.receive()
        return result.get(key, None)

    def get_multi(self, keys):
        result_channel = Channel()
        grouped = self._keys_to_addr(keys).items()
        n = len(grouped)
        for addr, _keys in grouped:
            defer(self._connect_by_addr, addr, _keys, result_channel)
        for connection, _keys in result_channel.receive_n(n):
            defer(self._write_command, connection, "get", [_keys], result_channel)
        result = {}        
        for _result in result_channel.receive_n(n):
            result.update(_result)
        return result

 
                    




            

