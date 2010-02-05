# Copyright (C) 2009, Hyves (Startphone Ltd.)
#
# This module is part of the Concurrence Framework and is released under
# the New BSD License: http://www.opensource.org/licenses/bsd-license.php

import unittest
import logging
import time

from concurrence import dispatch, Tasklet, Channel, quit
from concurrence.core import EXIT_CODE_TIMEOUT

from concurrence.io import IOStream, Socket

class TestSocket(object):

    _installed = {}

    def __init__(self, callback):
        self._step_count = 0
        self._address = None
        self._callback = callback

    def _step(self, event, args, kwargs):
        res = self._callback(self, self._step_count, event, args, kwargs)
        self._step_count += 1
        return res

    def _connect(self, *args, **kwargs):
        self._address = args[0]
        res = self._step("connect", args, kwargs)
        return res

    def close(self, *args, **kwargs):
        return self._step("close", args, kwargs)

    def write(self, *args, **kwargs):
        res = self._step("write", args, kwargs)
        if res is None: #by default read bytes
            return len(args[0].read_bytes(-1))

    def read(self, *args, **kwargs):
        res = self._step("read", args, kwargs)
        if res is None:
            return 0 #0 bytes read by default
        else:
            args[0].write_bytes(res)
            return len(res)

    @classmethod
    def install(cls, addr, callback):
        cls._installed[addr] = TestSocket(callback)
        def interceptor(addr):
            return cls._installed[addr]
        Socket.set_interceptor(interceptor)


class TestCase(unittest.TestCase):
    def setUp(self):
        logging.debug("setUp %s", self)

    def tearDown(self):
        try:
            Tasklet.yield_() #this make sure that everything gets a change to exit before we start the next test
            logging.debug("tearDown %s, tasklet count #%d", self, Tasklet.count())
        except:
            pass

class _Timer:
    def __enter__(self):
        self._start = time.time()
        return self

    def __exit__(self, type, value, traceback):
        self._end = time.time()

    def __str__(self):
        self._end - self._start

    def sec(self, n):
        return n / (self._end - self._start)

def timer():
    return _Timer()

def main(timeout = None):

    logging.basicConfig()
    logging.root.setLevel(logging.DEBUG)

    if timeout is not None:
        def quit_test():
            logging.error("quiting unittest on timeout")
            quit(EXIT_CODE_TIMEOUT)
        logging.debug("test will timeout in %s seconds", timeout)
        timeout_task = Tasklet.later(timeout, quit_test, name = 'unittest_timeout')()

    from concurrence.core import _profile
    #_profile(unittest.main)
    dispatch(unittest.main)

