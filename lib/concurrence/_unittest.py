# Copyright (C) 2009, Hyves (Startphone Ltd.)
#
# This module is part of the Concurrence Framework and is released under
# the New BSD License: http://www.opensource.org/licenses/bsd-license.php

import unittest
import logging
import time

from concurrence import dispatch, Tasklet, quit 
from concurrence.core import EXIT_CODE_TIMEOUT

from concurrence.io import IOStream


class TestCase(unittest.TestCase):
    def setUp(self):
        logging.debug(self)

    def tearDown(self):
        try:
            Tasklet.yield_() #this make sure that everything gets a change to exit before we start the next test
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

