from __future__ import with_statement

import time

from concurrence import unittest, Tasklet, Channel, TimeoutError, TIMEOUT_NEVER, TIMEOUT_CURRENT
from concurrence.timer import Timeout

class TestTimer(unittest.TestCase):
    def testPushPop(self):

        self.assertEquals(TIMEOUT_NEVER, Timeout.current())

        Timeout.push(30)
        self.assertAlmostEqual(30, Timeout.current(), places = 1)
        Timeout.pop()
        self.assertEquals(TIMEOUT_NEVER, Timeout.current())
        Timeout.push(30)
        self.assertAlmostEqual(30, Timeout.current(), places = 1)
        Tasklet.sleep(1.0)
        self.assertAlmostEqual(29, Timeout.current(), places = 1)
        #push a temporary short timeout
        Timeout.push(5)
        self.assertAlmostEqual(5, Timeout.current(), places = 1)
        Timeout.pop()
        self.assertAlmostEqual(29, Timeout.current(), places = 1)

        #try to push a new longer timeout than the parent timeout
        #this should fail, e.g. it will keep the parent timeout
        Timeout.push(60)
        self.assertAlmostEqual(29, Timeout.current(), places = 1)
        Timeout.pop()
        self.assertAlmostEqual(29, Timeout.current(), places = 1)
        Timeout.pop()
        self.assertEquals(TIMEOUT_NEVER, Timeout.current())

    def testPushPop2(self):

        self.assertEquals(TIMEOUT_NEVER, Timeout.current())
        Timeout.push(TIMEOUT_NEVER)
        self.assertEquals(TIMEOUT_NEVER, Timeout.current())
        Timeout.pop()
        self.assertEquals(TIMEOUT_NEVER, Timeout.current())

        Timeout.push(10)
        self.assertAlmostEqual(10, Timeout.current(), places = 1)
        Timeout.push(5)
        self.assertAlmostEqual(5, Timeout.current(), places = 1)
        Timeout.pop()
        self.assertAlmostEqual(10, Timeout.current(), places = 1)
        Timeout.pop()
        self.assertEquals(TIMEOUT_NEVER, Timeout.current())

    def testPushPop3(self):
        self.assertEquals(TIMEOUT_NEVER, Timeout.current())
        Tasklet.set_current_timeout(10.0)
        Timeout.push(5.0)
        self.assertAlmostEqual(5.0, Timeout.current(), places = 1)
        Timeout.pop()
        self.assertAlmostEqual(10.0, Timeout.current(), places = 1)
        Timeout.push(15.0)
        self.assertAlmostEqual(10.0, Timeout.current(), places = 1)
        Timeout.pop()
        self.assertAlmostEqual(10.0, Timeout.current(), places = 1)
        self.assertAlmostEqual(10.0, Tasklet.get_current_timeout(), places = 1)
        Tasklet.set_current_timeout(TIMEOUT_NEVER)

    def testPushPop4(self):
        self.assertEquals(TIMEOUT_NEVER, Timeout.current())
        Tasklet.set_current_timeout(10.0)
        self.assertAlmostEqual(10.0, Timeout.current(), places = 1)
        Timeout.push(TIMEOUT_CURRENT)
        self.assertAlmostEqual(10.0, Timeout.current(), places = 1)
        Timeout.pop()
        self.assertAlmostEqual(10.0, Timeout.current(), places = 1)
        Tasklet.set_current_timeout(TIMEOUT_NEVER)

    def testTimer(self):

        ch = Channel()

        def sender(times):
            for i in range(times):
                Tasklet.sleep(1.0)
                ch.send(True)

        with Timeout.push(10):
            Tasklet.new(sender)(4)
            for i in range(4):
                ch.receive(Timeout.current())

        start = time.time()
        try:
            with Timeout.push(2.5):
                Tasklet.new(sender)(4)
                for i in range(4):
                    ch.receive(Timeout.current())
                self.fail('expected timeout')
        except TimeoutError, e:
            end = time.time()
            self.assertAlmostEqual(2.5, end - start, places = 1)


if __name__ == '__main__':
    unittest.main(timeout = 10)
