
import logging
import time
import sys

from concurrence import unittest, Tasklet, Channel, TaskletPool, Deque, TimeoutError, TaskletError, JoinError, Message

class TestTaskletPool(unittest.TestCase):
    def testBasic(self):

        d = Deque()

        def handler(i):
            Tasklet.sleep(1.0)
            d.append(i)

        tp = TaskletPool(5)

        for i in range(20):
            tp.defer(handler, i)
 
        start = time.time()

        xs = []
        while True:
            xs.append(d.popleft(True, 30))
            if len(xs) == 20:
                break
        
        end = time.time()
        
        #5 workers taking 1 second to process 20 items = 4.0 total proc time
        self.assertAlmostEqual(4.0, end - start, places = 1)
        self.assertEquals(190, sum(xs))

if __name__ == '__main__':
    unittest.main(timeout = 100.0)
