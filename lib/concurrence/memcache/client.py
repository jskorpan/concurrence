# Copyright (C) 2009, Hyves (Startphone Ltd.)
#
# This module is part of the Concurrence Framework and is released under
# the New BSD License: http://www.opensource.org/licenses/bsd-license.php
from __future__ import with_statement

from concurrence import Tasklet, Channel, DeferredQueue
from concurrence.io import Socket, BufferedStream
from concurrence.containers.deque import Deque

from concurrence.memcache import MemcacheResultCode
from concurrence.memcache.codec import Codec
from concurrence.memcache.behaviour import MemcacheBehaviour, MemcacheKetamaBehaviour

#TODO:

#timeout on commands (test tasklet based timeout)
#statistics
#gzip support
#close unused connections
#proper buffer sizes
#not use pickle for string and unicode types (use flags to indicate this)
#norepy e.g. no server response to set commands
#stats cmd (+item + item size stats

#what to do with partial multi get failure accross multiple servers?, e.g. return partial keys?

#bundling of multiple requests in 1 flush (autoflush on/off)
#todo detect timeouts on write/read, and mark host as dead
#keep some time before retrying host
#close down node no recv ERROR?
#UPD support
#binary support
#how to handle timouts in the pipelined case?
#TODO validate keys!, they are 'txt' not random bins!, e.g. some chars not allowed, which ones?
#CLAMP timestamps at 2**31-1
#CHECK KEY MAX LEN, VAL MAX VALUE LEN, VALID KEY

class MemcacheProtocol(object):
    @classmethod
    def create(cls, type_):
        if type_ == 'text':
            return MemcacheTextProtocol()
        else:
            assert False, "unknown protocol"

class MemcacheTextProtocol(MemcacheProtocol):
    def __init__(self, codec = "default"):
        self.set_codec(codec)

    def set_codec(self, codec):
        self._codec = Codec.create(codec)

    def _read_result(self, reader):
        response_line = reader.read_line()
        return MemcacheResultCode.get(response_line)

    def write_version(self, writer):
        writer.write_bytes("version\r\n")

    def read_version(self, reader):
        response_line = reader.read_line()
        if response_line.startswith('VERSION'):
            return response_line[8:].strip()
        else:
            return MemcacheResultCode.get(response_line)

    def _write_storage(self, writer, cmd, key, value, cas_unique = None):
        encoded_value, flags = self._codec.encode(value)
        if cas_unique is not None:
            writer.write_bytes("%s %s %d 0 %d %d\r\n%s\r\n" % (cmd, key, flags, len(encoded_value), cas_unique, encoded_value))
        else:
            writer.write_bytes("%s %s %d 0 %d\r\n%s\r\n" % (cmd, key, flags, len(encoded_value), encoded_value))

    def write_cas(self, writer, key, value, cas_unique):
        self._write_storage(writer, "cas", key, value, cas_unique)

    def read_cas(self, reader):
        return self._read_result(reader)

    def _write_incdec(self, writer, cmd, key, value):
        writer.write_bytes("%s %s %s\r\n" % (cmd, key, value))

    def _read_incdec(self, reader):
        response_line = reader.read_line()
        try:
            return int(response_line)
        except ValueError:
            return MemcacheResultCode.get(response_line)

    def write_incr(self, writer, key, value):
        self._write_incdec(writer, "incr", key, value)

    def read_incr(self, reader):
        return self._read_incdec(reader)

    def write_decr(self, writer, key, value):
        self._write_incdec(writer, "decr", key, value)

    def read_decr(self, reader):
        return self._read_incdec(reader)

    def write_get(self, writer, keys):
        writer.write_bytes("get %s\r\n" % " ".join(keys))

    def write_gets(self, writer, keys):
        writer.write_bytes("gets %s\r\n" % " ".join(keys))

    def read_get(self, reader, with_cas_unique = False):
        result = {}
        while True:
            response_line = reader.read_line()
            if response_line.startswith('VALUE'):
                response_fields = response_line.split(' ')
                key = response_fields[1]
                flags = int(response_fields[2])
                n = int(response_fields[3])
                if with_cas_unique:
                    cas_unique = int(response_fields[4])
                encoded_value = reader.read_bytes(n)
                reader.read_line() #\r\n
                if with_cas_unique:
                    result[key] = (self._codec.decode(flags, encoded_value), cas_unique)
                else:
                    result[key] = self._codec.decode(flags, encoded_value)
            elif response_line == 'END':
                return result
            else:
                return MemcacheResultCode.get(response_line)

    def read_gets(self, reader):
        return self.read_get(reader, with_cas_unique = True)

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

    def write_append(self, writer, key, value):
        return self._write_storage(writer, "append", key, value)

    def read_append(self, reader):
        return self._read_result(reader)

    def write_prepend(self, writer, key, value):
        return self._write_storage(writer, "prepend", key, value)

    def read_prepend(self, reader):
        return self._read_result(reader)

class MemcacheTCPConnection(object):

    _read_timeout = 10
    _write_timeout = 10

    def __init__(self, protocol = "text", codec = "default"):
        self._read_queue = DeferredQueue()
        self._write_queue = DeferredQueue()
        self._stream = None

        if isinstance(protocol, MemcacheProtocol):
            self._protocol = protocol
        else:
            self._protocol = MemcacheProtocol.create(protocol)

        if self._protocol and codec:
            self._protocol.set_codec(codec)

    def connect(self, addr, timeout = -2):
        self._stream = BufferedStream(Socket.connect(addr, timeout))

    def defer_command(self, cmd, args, result_channel):
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

    def do_command(self, cmd, args):
        result_channel = Channel()
        self.defer_command(cmd, args, result_channel)
        return result_channel.receive()

    def delete(self, key):
        return self.do_command("delete", (key,))

    def set(self, key, data):
        return self.do_command("set", (key, data))

    def add(self, key, data):
        return self.do_command("add", (key, data))

    def replace(self, key, data):
        return self.do_command("replace", (key, data))

    def append(self, key, data):
        return self.do_command("append", (key, data))

    def prepend(self, key, data):
        return self.do_command("prepend", (key, data))

    def cas(self, key, data, cas_unique):
        return self.do_command("cas", (key, data, cas_unique))

    def incr(self, key, value):
        return self.do_command("incr", (key, value))

    def decr(self, key, value):
        return self.do_command("decr", (key, value))

    def get(self, key):
        result = self.do_command("get", ([key], ))
        return result.get(key, None)

    def get_multi(self, keys):
        return self.do_command("get", (keys, ))

    def gets(self, key):
        result = self.do_command("gets", ([key], ))
        return result.get(key, None)

    def gets_multi(self, keys):
        return self.do_command("gets", (keys, ))

    def version(self):
        return self.do_command("version", ())

class Memcache(object):
    def __init__(self, servers = None, codec = "default", behaviour = "ketama", protocol = "text"):

        self.read_timeout = 10
        self.write_timeout = 10
        self.connect_timeout = 2

        self._connections = {} #addr -> conn
        self._protocol = MemcacheProtocol.create(protocol)

        self._protocol.set_codec(codec)

        self._behaviour = MemcacheBehaviour.create(behaviour)
        self._key_to_addr = self._behaviour.key_to_addr

        if servers is not None:
            self.set_servers(servers)

    def set_servers(self, servers):
        self._behaviour.set_servers(servers)

    def _get_connection(self, addr):
        if not addr in self._connections:
            connection = MemcacheTCPConnection(self._protocol)
            connection.connect(addr)
            self._connections[addr] = connection
        return self._connections[addr]

    def _on_connect(self, connection):
        connection.set_protocol(self._protocol)

    def _connect_by_addr(self, addr, keys, result_channel):
        Tasklet.set_current_timeout(self.connect_timeout)
        connection = self._get_connection(addr)
        result_channel.send((connection, keys))

    def connection_for_key(self, key):
        return self._get_connection(self._key_to_addr(key))

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
        return self.connection_for_key(key).do_command("delete", (key,))

    def set(self, key, data):
        return self.connection_for_key(key).do_command("set", (key, data))

    def add(self, key, data):
        return self.connection_for_key(key).do_command("add", (key, data))

    def replace(self, key, data):
        return self.connection_for_key(key).do_command("replace", (key, data))

    def append(self, key, data):
        return self.connection_for_key(key).do_command("append", (key, data))

    def prepend(self, key, data):
        return self.connection_for_key(key).do_command("prepend", (key, data))

    def cas(self, key, data, cas_unique):
        return self.connection_for_key(key).do_command("cas", (key, data, cas_unique))

    def incr(self, key, value):
        return self.connection_for_key(key).do_command("incr", (key, value))

    def decr(self, key, value):
        return self.connection_for_key(key).do_command("decr", (key, value))

    def _get(self, cmd, key):
        result_channel = Channel()
        connection = self.connection_for_key(key)
        connection.defer_command(cmd, [[key]], result_channel)
        result = result_channel.receive()
        return result.get(key, None)

    def get(self, key):
        return self._get("get", key)

    def gets(self, key):
        return self._get("gets", key)

    def _get_multi(self, cmd, keys):
        result_channel = Channel()
        grouped = self._keys_to_addr(keys).items()
        n = len(grouped)
        for addr, _keys in grouped:
            Tasklet.defer(self._connect_by_addr, addr, _keys, result_channel)
        for connection, _keys in result_channel.receive_n(n):
            connection.defer_command(cmd, [_keys], result_channel)
        result = {}
        for _result in result_channel.receive_n(n):
            result.update(_result)
        return result

    def get_multi(self, keys):
        return self._get_multi("get", keys)

    def gets_multi(self, keys):
        return self._get_multi("gets", keys)







