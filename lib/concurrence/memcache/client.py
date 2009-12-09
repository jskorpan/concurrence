# Copyright (C) 2009, Hyves (Startphone Ltd.)
#
# This module is part of the Concurrence Framework and is released under
# the New BSD License: http://www.opensource.org/licenses/bsd-license.php
from __future__ import with_statement

import logging

from concurrence import Tasklet, Channel, DeferredQueue, TIMEOUT_CURRENT
from concurrence.io import Socket, BufferedStream
from concurrence.containers.deque import Deque

from concurrence.memcache import MemcacheError
from concurrence.memcache.codec import MemcacheCodec
from concurrence.memcache.behaviour import MemcacheBehaviour
from concurrence.memcache.protocol import MemcacheProtocol

#TODO:

#how to communicate and handle errors (raise error for get/gets?)
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


class MemcacheConnection(object):
    log = logging.getLogger("MemcacheConnection")

    _read_timeout = 10
    _write_timeout = 10

    def __init__(self, protocol = "text", codec = "default"):
        self._read_queue = DeferredQueue()
        self._write_queue = DeferredQueue()

        self._stream = None

        self._protocol = MemcacheProtocol.create(protocol)
        self._protocol.set_codec(MemcacheCodec.create(codec))

    def _defer_command(self, cmd, args, result_channel):
        def _read_result():
            Tasklet.set_current_timeout(self._read_timeout)
            try:
                with self._stream.get_reader() as reader:
                    result = getattr(self._protocol, 'read_' + cmd)(reader)
                result_channel.send(result)
            except TaskletExit:
                raise
            except:
                self.log.exception("read error in defer_command")
                result_channel.send_exception(MemcacheError, "while reading result")

        def _write_command():
            Tasklet.set_current_timeout(self._write_timeout)
            try:
                with self._stream.get_writer() as writer:
                    getattr(self._protocol, 'write_' + cmd)(writer, *args)
                    writer.flush()
                    self._read_queue.defer(_read_result)
            except TaskletExit:
                raise
            except:
                self.log.exception("write error in defer_command")
                result_channel.send_exception(MemcacheError, "while writing command")

        self._write_queue.defer(_write_command)

    def _do_command(self, cmd, args):
        result_channel = Channel()
        self._defer_command(cmd, args, result_channel)
        return result_channel.receive()

    def connect(self, addr, timeout = TIMEOUT_CURRENT):
        self._stream = BufferedStream(Socket.connect(addr, timeout))

    def close(self):
        del self._read_queue
        del self._write_queue
        del self._protocol
        self._stream.close()

    def delete(self, key, expiration = 0):
        return self._do_command("delete", (key, expiration))

    def set(self, key, data, expiration = 0, flags = 0):
        return self._do_command("set", (key, data, expiration, flags))

    def add(self, key, data, expiration = 0, flags = 0):
        return self._do_command("add", (key, data, expiration, flags))

    def replace(self, key, data, expiration = 0, flags = 0):
        return self._do_command("replace", (key, data, expiration, flags))

    def append(self, key, data, expiration = 0, flags = 0):
        return self._do_command("append", (key, data, expiration, flags))

    def prepend(self, key, data, expiration = 0, flags = 0):
        return self._do_command("prepend", (key, data, expiration, flags))

    def cas(self, key, data, cas_unique, expiration = 0, flags = 0):
        return self._do_command("cas", (key, data, expiration, flags, cas_unique))

    def incr(self, key, value):
        return self._do_command("incr", (key, value))

    def decr(self, key, value):
        return self._do_command("decr", (key, value))

    def get(self, key, default = None):
        #TODO how to return flags?, also for multi and gets
        result = self._do_command("get", ([key], ))
        return result.get(key, default)

    def gets(self, key, default = None):
        result = self._do_command("gets", ([key], ))
        return result.get(key, default)

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
        self._connecting = {} #address -> Channel

    def get_connection(self, addr, protocol):
        """gets a connection to memcached servers at given address using given protocol."""
        #note that this method is complicated by the fact that the .connect method can potentially block
        #allowing other tasklets to arrive here concurrently.
        #only the first tasklet will be responsible for opening the connection, if another tasklet comes in at the
        #same time, it put on hold on a channel and will wait for the first tasklet to return the connection
        if addr in self._connections:
            return self._connections[addr]
        else:
            if addr in self._connecting:
                #somebody else is already connecting, it will inform us of the connection
                return self._connecting[addr].receive()
            else:
                #i am the one who will open the connection
                self._connecting[addr] = Channel()
                connection = MemcacheConnection(protocol)
                connection.connect(addr)
                self._connections[addr] = connection
                connect_channel = self._connecting[addr]
                del self._connecting[addr]
                #inform other waiting tasklets of the new connection
                while connect_channel.has_receiver():
                    connect_channel.send(connection)
                return connection

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

    def _connect_by_addr(self, addr, keys, result_channel):
        Tasklet.set_current_timeout(self.connect_timeout)
        connection = self._get_connection(addr)
        result_channel.send((connection, keys))

    def _get(self, cmd, key, default):
        result_channel = Channel()
        connection = self.connection_for_key(key)
        connection._defer_command(cmd, [[key]], result_channel)
        result = result_channel.receive()
        return result.get(key, default)

    def _get_multi(self, cmd, keys):
        result_channel = Channel()

        #group keys by address (address->[keys]):
        grouped_addrs = {}
        for key in keys:
            addr = self._key_to_addr(key)
            grouped_addrs.setdefault(addr, []).append(key)

        #n is the number of servers we need to 'get' from
        n = len(grouped_addrs)

        #get connections to all servers asynchronously and in parallel, connections and corresponding keys are returned on return_channel
        for addr, _keys in grouped_addrs.iteritems():
            Tasklet.defer(self._connect_by_addr, addr, _keys, result_channel)
        #now asynchronously and in parallel fetch the values from each server
        for connection, _keys in result_channel.receive_n(n):
            connection._defer_command(cmd, [_keys], result_channel)
        #loop over the results as they come in and aggregate the final result
        result = {}
        for _result in result_channel.receive_n(n):
            result.update(_result)
        return result

    def set_servers(self, servers = None):
        if servers is not None:
            self._behaviour.set_servers(servers)

    def connection_for_key(self, key):
        return self._get_connection(self._key_to_addr(key))

    def delete(self, key, expiration = 0):
        return self.connection_for_key(key)._do_command("delete", (key, expiration))

    def set(self, key, data, expiration = 0, flags = 0):
        return self.connection_for_key(key)._do_command("set", (key, data, expiration, flags))

    def add(self, key, data, expiration = 0, flags = 0):
        return self.connection_for_key(key)._do_command("add", (key, data, expiration, flags))

    def replace(self, key, data, expiration = 0, flags = 0):
        return self.connection_for_key(key)._do_command("replace", (key, data, expiration, flags))

    def append(self, key, data, expiration = 0, flags = 0):
        return self.connection_for_key(key)._do_command("append", (key, data, expiration, flags))

    def prepend(self, key, data, expiration = 0, flags = 0):
        return self.connection_for_key(key)._do_command("prepend", (key, data, expiration, flags))

    def cas(self, key, data, cas_unique, expiration = 0, flags = 0):
        return self.connection_for_key(key)._do_command("cas", (key, data, expiration, flags, cas_unique))

    def incr(self, key, value):
        return self.connection_for_key(key)._do_command("incr", (key, value))

    def decr(self, key, value):
        return self.connection_for_key(key)._do_command("decr", (key, value))

    def get(self, key, default = None):
        return self._get("get", key, default)

    def gets(self, key, default = None):
        return self._get("gets", key, default)

    def get_multi(self, keys):
        return self._get_multi("get", keys)

    def gets_multi(self, keys):
        return self._get_multi("gets", keys)

