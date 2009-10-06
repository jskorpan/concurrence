# Copyright (C) 2009, Hyves (Startphone Ltd.)
#
# This module is part of the Concurrence Framework and is released under
# the New BSD License: http://www.opensource.org/licenses/bsd-license.php

class MemcacheResultCode(object):
    _all = {}

    def __init__(self, name):
        self._name = name
        self._all[name] = self
    
    def __repr__(self):
        return "<MemcacheResultCode: %s>" % self._name
        
    @classmethod
    def get(cls, name, default):
        return cls._all.get(name, default)

MemcacheResultCode.STORED = MemcacheResultCode("STORED")
MemcacheResultCode.NOT_STORED = MemcacheResultCode("NOT_STORED")
MemcacheResultCode.EXISTS = MemcacheResultCode("EXISTS")
MemcacheResultCode.NOT_FOUND = MemcacheResultCode("NOT_FOUND")
MemcacheResultCode.DELETED = MemcacheResultCode("DELETED")
MemcacheResultCode.ERROR = MemcacheResultCode("ERROR")

from concurrence.memcache.client import Memcache

            

