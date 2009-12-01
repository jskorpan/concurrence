# Copyright (C) 2009, Hyves (Startphone Ltd.)
#
# This module is part of the Concurrence Framework and is released under
# the New BSD License: http://www.opensource.org/licenses/bsd-license.php

class MemcacheError(Exception): 
    pass

class MemcacheResultCode(object):
    """type safe enumeration of memcache result codes"""
    _all = {}

    def __init__(self, name, msg = ''):
        self._name = name
        self._all[name] = self
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
        code = cls._all.get(line, None)
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

MemcacheResultCode.STORED = MemcacheResultCode("STORED")
MemcacheResultCode.NOT_STORED = MemcacheResultCode("NOT_STORED")
MemcacheResultCode.EXISTS = MemcacheResultCode("EXISTS")
MemcacheResultCode.NOT_FOUND = MemcacheResultCode("NOT_FOUND")
MemcacheResultCode.DELETED = MemcacheResultCode("DELETED")
MemcacheResultCode.ERROR = MemcacheResultCode("ERROR")

from concurrence.memcache.client import Memcache, MemcacheTCPConnection

            

