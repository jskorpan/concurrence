# Copyright (C) 2009, Hyves (Startphone Ltd.)
#
# This module is part of the Concurrence Framework and is released under
# the New BSD License: http://www.opensource.org/licenses/bsd-license.php
from __future__ import with_statement

from concurrence import Tasklet, Channel, Message, TaskletPool, DeferredQueue, TaskletError
from concurrence.timer import Timeout
from concurrence.io import Socket, Buffer
from concurrence.io.buffered import BufferedStreamShared
from concurrence.containers.deque import Deque

from concurrence.memcache import MemcacheResultCode
from concurrence.memcache.codec import DefaultCodec, RawCodec
from concurrence.memcache.behaviour import MemcacheKetamaBehaviour

import logging
import cPickle as pickle
from collections import deque

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
#CLAMP timestamps at 2**31-1
#CHECK KEY MAX LEN, VAL MAX VALUE LEN, VALID KEY

class MemcacheTextProtocol(object):
    def __init__(self, codec = None):
        self._codec = codec

    def _read_result(self, reader):
        response_line = reader.read_line()
        result = MemcacheResultCode.get(response_line, None)
        assert result is not None, "protocol error"
        return result

    def _write_storage(self, writer, cmd, key, value):
        encoded_value, flags = self._codec.encode(value)
        writer.write_bytes("%s %s %d 0 %d\r\n%s\r\n" % (cmd, key, flags, len(encoded_value), encoded_value))

    def write_get(self, writer, keys):
        writer.write_bytes("get %s\r\n" % " ".join(keys))

    def read_get(self, reader):
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
    #_write_buffer_size = 1024
    #_read_buffer_size = 1024 * 16
    _read_timeout = 10
    _write_timeout = 10

    def __init__(self, stream, protocol = None):
        self._read_queue = DeferredQueue()
        self._write_queue = DeferredQueue()
        self._stream = BufferedStreamShared(stream)
        self._protocol = protocol

    def set_protocol(self, protocol):
        self._protocol = protocol

    def do_command(self, cmd, args, result_channel):
        def _read_result():
            Tasklet.set_current_timeout(self._read_timeout)
            with self._stream.get_reader() as reader:
                result = getattr(self._protocol, 'read_' + cmd)(reader)
            result_channel.send(result)

        def _write_command():
            Tasklet.set_current_timeout(self._write_timeout)
            with self._stream.get_writer() as writer:
                getattr(self._protocol, 'write_' + cmd)(writer, *args)
                writer.flush()
                self._read_queue.defer(_read_result)

        self._write_queue.defer(_write_command)

class _MemcacheTCPConnectionManager(object):
    NUM_CONNECTIONS_PER_ADDRESS = 2

    def __init__(self, on_connect_callback):
        self._connections = {} #addr -> deque([conns])
        self._connecting = {} #addr -> count
        self._on_connect_callback = on_connect_callback

    def get_connection(self, addr):
        if not addr in self._connections:
            self._connections[addr] = deque()
            self._connecting[addr] = 0
        connections = self._connections[addr]
        if (len(connections) + self._connecting[addr]) < self.NUM_CONNECTIONS_PER_ADDRESS:
            #TODO try/finally for self._connecting
            self._connecting[addr] += 1
            connection = _MemcacheTCPConnection(Socket.connect(addr, -2))
            self._on_connect_callback(connection)
            connection.addr = addr
            self._connections[addr].appendleft(connection)
            self._connecting[addr] -= 1
        connection = self._connections[addr][0]
        self._connections[addr].rotate()
        return connection

class Memcache(object):
    def __init__(self, servers = None):
        self.read_timeout = 10
        self.write_timeout = 10
        self.connect_timeout = 2

        self._protocol = MemcacheTextProtocol()
        self._connection_manager = _MemcacheTCPConnectionManager(self._on_connect) #TODO make overridable singleton

        self.set_codec(DefaultCodec())
        self.set_behaviour(MemcacheKetamaBehaviour()) #default

        if servers is not None:
            self.set_servers(servers)

    def _on_connect(self, connection):
        connection.set_protocol(self._protocol)

    def set_codec(self, codec):
        self._codec = codec
        self._protocol._codec = codec

    def set_behaviour(self, behaviour):
        self._behaviour = behaviour
        self._key_to_addr = behaviour.key_to_addr

    def set_servers(self, servers):
        self._behaviour.set_servers(servers)

    def _connect_by_addr(self, addr, keys, result_channel):
        Tasklet.set_current_timeout(self.connect_timeout)
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
        connection = self._connect_by_key(args[0])
        connection.do_command(cmd, args, result_channel)
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
        connection = self._connect_by_key(key)
        connection.do_command("get", [[key]], result_channel)
        result = result_channel.receive()
        return result.get(key, None)

    def get_multi(self, keys):
        result_channel = Channel()
        grouped = self._keys_to_addr(keys).items()
        n = len(grouped)
        for addr, _keys in grouped:
            Tasklet.defer(self._connect_by_addr, addr, _keys, result_channel)
        for connection, _keys in result_channel.receive_n(n):
            connection.do_command("get", [_keys], result_channel)
        result = {}
        for _result in result_channel.receive_n(n):
            result.update(_result)
        return result









