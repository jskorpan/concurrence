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
    _old_socket_new = None
    _callback_channel = None
    _result_channel = None
    _step_count = 0

    def __init__(self, *args, **kwargs):
        pass

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

    @classmethod
    def install(cls):
        cls._old_socket_new = Socket.__new__
        Socket.__new__ = TestSocket

    @classmethod
    def uninstall(cls):
        Socket.__new__ = Socket

    def _step(self, name, args, kwargs):
        class Step(object):
            def match(self, address, name, count):
                return self.address == address and self.name == name and self.count == count
            def next(self, result = None):
                TestSocket._result_channel.send(result)
        TestSocket._step_count += 1
        step = Step()
        step.name = name
        step.args = args
        step.kwargs = kwargs
        step.count = TestSocket._step_count
        step.address = self._address
        TestSocket._callback_channel.send(step)
        res = TestSocket._result_channel.receive()
        return res


    @classmethod
    def test(cls):
        cls._callback_channel = Channel()
        cls._result_channel = Channel()
        cls._step_count = 0
        while True:
            yield cls._callback_channel.receive()


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

    dispatch(unittest.main)

