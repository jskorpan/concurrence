# Copyright (C) 2009, Hyves (Startphone Ltd.)
#
# This module is part of the Concurrence Framework and is released under
# the New BSD License: http://www.opensource.org/licenses/bsd-license.php

class MemcacheError(Exception):
    pass

class MemcacheResultCode(object):
    """type safe enumeration of memcache result codes"""
    _static = {}

    def __init__(self, name, msg = ''):
        self._name = name
        self._msg = msg

    @property
    def msg(self):
        return self._msg

    def __repr__(self):
        return "<MemcacheResultCode: %s>" % self._name

    def __eq__(self, other):
        return isinstance(other, MemcacheResultCode) and other._name == self._name

    @classmethod
    def get(cls, line):
        code = cls._static.get(line, None)
        if code is None:
            #try client or server error
            if line.startswith('CLIENT_ERROR'):
                return MemcacheResultCode("CLIENT_ERROR", line[13:])
            elif line.startswith('SERVER_ERROR'):
                return MemcacheResultCode("SERVER_ERROR", line[13:])
            else:
                raise MemcacheError("unknown response: %s" % repr(line))
        else:
            return code

    @classmethod
    def _add_static(cls, name):
        cls._static[name] = MemcacheResultCode(name)
        return cls._static[name]

MemcacheResultCode.STORED = MemcacheResultCode._add_static("STORED")
MemcacheResultCode.NOT_STORED = MemcacheResultCode._add_static("NOT_STORED")
MemcacheResultCode.EXISTS = MemcacheResultCode._add_static("EXISTS")
MemcacheResultCode.NOT_FOUND = MemcacheResultCode._add_static("NOT_FOUND")
MemcacheResultCode.DELETED = MemcacheResultCode._add_static("DELETED")
MemcacheResultCode.ERROR = MemcacheResultCode._add_static("ERROR")
MemcacheResultCode.TIMEOUT = MemcacheResultCode._add_static("TIMEOUT")

from concurrence.memcache.client import Memcache, MemcacheConnection, MemcacheConnectionManager
from concurrence.memcache.behaviour import MemcacheBehaviour
from concurrence.memcache.protocol import MemcacheProtocol
from concurrence.memcache.codec import MemcacheCodec
