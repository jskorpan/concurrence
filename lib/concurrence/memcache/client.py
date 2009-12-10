# Copyright (C) 2009, Hyves (Startphone Ltd.)
#
# This module is part of the Concurrence Framework and is released under
# the New BSD License: http://www.opensource.org/licenses/bsd-license.php
from __future__ import with_statement

import logging

from concurrence import Tasklet, Channel, DeferredQueue, TIMEOUT_CURRENT
from concurrence.io import Socket, BufferedStream

from concurrence.memcache import MemcacheError, MemcacheResult
from concurrence.memcache.codec import MemcacheCodec
from concurrence.memcache.behaviour import MemcacheBehaviour
from concurrence.memcache.protocol import MemcacheProtocol

#TODO:

#how to communicate and handle errors (raise error for get/gets?) and or extra stuff like flags?
#timeout on commands (test tasklet based timeout)
#statistics
#gzip support
#close unused connections
#proper buffer sizes
#norepy e.g. no server response to set commands, what is the fastest fill rate agains a single memcached server?
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


class MemcacheConnection(object):
    log = logging.getLogger("MemcacheConnection")

    _read_timeout = 10
    _write_timeout = 10

    def __init__(self, address, protocol = "text", codec = "default"):

        self._address = address

        self._stream = None
        self._read_queue = DeferredQueue()
        self._write_queue = DeferredQueue()

        self._protocol = MemcacheProtocol.create(protocol)
        self._protocol.set_codec(MemcacheCodec.create(codec))

    def connect(self):
        self._stream = BufferedStream(Socket.connect(self._address))

    def is_connected(self):
        return self._stream is not None

    def flush(self):
        self._stream.flush()

    def _write_command(self, cmd, args, flush = True):
        with self._stream.get_writer() as writer:
            getattr(self._protocol, 'write_' + cmd)(writer, *args)
            if flush:
                writer.flush()

    def _read_result(self, cmd):
        with self._stream.get_reader() as reader:
            return getattr(self._protocol, 'read_' + cmd)(reader)

    def _defer_command(self, cmd, args, result_channel, error_value = None):
        def _read_result():
            Tasklet.set_current_timeout(self._read_timeout)
            try:
                result_channel.send(self._read_result(cmd))
            except TaskletExit:
                raise
            except:
                self.log.exception("read error in defer_command")
                result_channel.send((MemcacheResult.ERROR, error_value))

        def _write_command():
            Tasklet.set_current_timeout(self._write_timeout)
            try:
                if not self.is_connected():
                    self.connect()
                self._write_command(cmd, args, True)
                self._read_queue.defer(_read_result)
            except TaskletExit:
                raise
            except:
                self.log.exception("write error in defer_command")
                result_channel.send((MemcacheResult.ERROR, error_value))

        self._write_queue.defer(_write_command)

    def _do_command(self, cmd, args, error_value = None):
        result_channel = Channel()
        self._defer_command(cmd, args, result_channel, error_value)
        return result_channel.receive()

    def close(self):
        if self.is_connected():
            self._stream.close()
            self._stream = None

    def delete(self, key, expiration = 0):
        return self._do_command("delete", (key, expiration))[0]

    def set(self, key, data, expiration = 0, flags = 0):
        return self._do_command("set", (key, data, expiration, flags))[0]

    def __setitem__(self, key, data):
        self.set(key, data)

    def add(self, key, data, expiration = 0, flags = 0):
        return self._do_command("add", (key, data, expiration, flags))[0]

    def replace(self, key, data, expiration = 0, flags = 0):
        return self._do_command("replace", (key, data, expiration, flags))[0]

    def append(self, key, data, expiration = 0, flags = 0):
        return self._do_command("append", (key, data, expiration, flags))[0]

    def prepend(self, key, data, expiration = 0, flags = 0):
        return self._do_command("prepend", (key, data, expiration, flags))[0]

    def cas(self, key, data, cas_unique, expiration = 0, flags = 0):
        return self._do_command("cas", (key, data, expiration, flags, cas_unique))[0]

    def incr(self, key, increment):
        return self._do_command("incr", (key, increment))

    def decr(self, key, increment):
        return self._do_command("decr", (key, increment))

    def get(self, key, default = None):
        _, values = self._do_command("get", ([key], ), {})
        return values.get(key, default)

    def __getitem__(self, key):
        return self.get(key)

    def getr(self, key, default = None):
        result, values = self._do_command("get", ([key], ), {})
        return result, values.get(key, default)

    def gets(self, key, default = None):
        result, values = self._do_command("gets", ([key], ), {})
        value, cas_unique = values.get(key, (default, None))
        return result, value, cas_unique

    def get_multi(self, keys):
        return self._do_command("get", (keys, ))

    def gets_multi(self, keys):
        return self._do_command("gets", (keys, ))

    def version(self):
        return self._do_command("version", ())

class MemcacheConnectionManager(object):
    _instance = None #TODO when we support multiple protocols, we need to have 1 instance per protocol

    def __init__(self):
        self._connections = {} #address -> connection

    def get_connection(self, address, protocol):
        """gets a connection to memcached servers at given address using given protocol."""
        if not address in self._connections:
            self._connections[address] = MemcacheConnection(address, protocol)
        return self._connections[address]

    def close_all(self):
        for connection in self._connections.values():
            connection.close()
        self._connections = {}

    @classmethod
    def create(cls, type_):
        if isinstance(type_, MemcacheConnectionManager):
            return type_
        elif type_ == "default":
            if cls._instance is None:
                cls._instance = MemcacheConnectionManager()
            return cls._instance
        else:
            raise MemcacheError("connection manager: %s" % type_)

class Memcache(object):
    def __init__(self, servers = None, codec = "default", behaviour = "ketama", protocol = "text", connection_manager = "default"):

        self.read_timeout = 10
        self.write_timeout = 10
        self.connect_timeout = 2

        self._protocol = MemcacheProtocol.create(protocol)
        self._protocol.set_codec(codec)

        self._connection_manager = MemcacheConnectionManager.create(connection_manager)

        self._behaviour = MemcacheBehaviour.create(behaviour)
        self._key_to_addr = self._behaviour.key_to_addr

        self.set_servers(servers)

    def _get_connection(self, addr):
        return self._connection_manager.get_connection(addr, self._protocol)

    def _get(self, cmd, key, default):
        result_channel = Channel()
        connection = self.connection_for_key(key)
        connection._defer_command(cmd, [[key]], result_channel, {})
        result, values = result_channel.receive()
        return result, values.get(key, default)

    def _get_multi(self, cmd, keys):


        #group keys by address (address->[keys]):
        grouped_addrs = {}
        for key in keys:
            addr = self._key_to_addr(key)
            grouped_addrs.setdefault(addr, []).append(key)

        #n is the number of servers we need to 'get' from
        n = len(grouped_addrs)

        result_channel = Channel()

        for address, _keys in grouped_addrs.iteritems():
            connection = self._get_connection(address)
            connection._defer_command(cmd, [_keys], result_channel, {})

        #loop over the results as they come in and aggregate the final result
        values = {}
        result = MemcacheResult.OK
        for _result, _values in result_channel.receive_n(n):
            if MemcacheResult.OK is _result:
                values.update(_values)
            else:
                result = _result #document that we only return the last not OK result
        return result, values

    def set_servers(self, servers = None):
        if servers is not None:
            self._behaviour.set_servers(servers)

    def connection_for_key(self, key):
        return self._get_connection(self._key_to_addr(key))

    def delete(self, key, expiration = 0):
        return self.connection_for_key(key)._do_command("delete", (key, expiration))[0]

    def set(self, key, data, expiration = 0, flags = 0):
        return self.connection_for_key(key)._do_command("set", (key, data, expiration, flags))[0]

    def __setitem__(self, key, data):
        self.set(key, data)

    def add(self, key, data, expiration = 0, flags = 0):
        return self.connection_for_key(key)._do_command("add", (key, data, expiration, flags))[0]

    def replace(self, key, data, expiration = 0, flags = 0):
        return self.connection_for_key(key)._do_command("replace", (key, data, expiration, flags))[0]

    def append(self, key, data, expiration = 0, flags = 0):
        return self.connection_for_key(key)._do_command("append", (key, data, expiration, flags))[0]

    def prepend(self, key, data, expiration = 0, flags = 0):
        return self.connection_for_key(key)._do_command("prepend", (key, data, expiration, flags))[0]

    def cas(self, key, data, cas_unique, expiration = 0, flags = 0):
        return self.connection_for_key(key)._do_command("cas", (key, data, expiration, flags, cas_unique))[0]

    def incr(self, key, increment):
        return self.connection_for_key(key)._do_command("incr", (key, increment))

    def decr(self, key, increment):
        return self.connection_for_key(key)._do_command("decr", (key, increment))

    def get(self, key, default = None):
        return self._get("get", key, default)[1]

    def __getitem__(self, key):
        return self.get(key)

    def getr(self, key, default = None):
        return self._get("get", key, default)

    def gets(self, key, default = None):
        result, (value, cas_unique) = self._get("gets", key, (default, None))
        return result, value, cas_unique

    def get_multi(self, keys):
        return self._get_multi("get", keys)

    def gets_multi(self, keys):
        return self._get_multi("gets", keys)

