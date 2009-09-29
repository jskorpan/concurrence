
import logging
import time
import sys

from concurrence import unittest, Tasklet, Channel, Lock, TaskletPool, Deque, TimeoutError, TaskletError, JoinError, Message

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

class TestLock(unittest.TestCase):        
    def testLock(self):
        lock = Lock()
        self.assertEquals(True, lock.acquire())   
        self.assertEquals(True, lock.is_locked())    
        self.assertEquals(None, lock.release())

        xs = []

        def t(x):
            try:
                with lock:
                    Tasklet.sleep(1.0)
                    xs.append(x)
                return x
            except TimeoutError:
                pass

        start = time.time()
        for i in range(5):
            Tasklet.new(t)(i)

        join_result = Tasklet.join_children()
        self.assertEquals(5, len(join_result))
        self.assertEquals(10, sum(xs))

        end = time.time()
        self.assertAlmostEqual(5.0, end - start, places = 1)

if __name__ == '__main__':
    unittest.main(timeout = 100.0)
