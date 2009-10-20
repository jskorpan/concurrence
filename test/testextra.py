from __future__ import with_statement

import logging
import time
import sys

from concurrence import unittest, Tasklet, Channel, Lock, Semaphore, TaskletPool, DeferredQueue, Deque, TimeoutError, TaskletError, JoinError, Message

class TestTaskletPool(unittest.TestCase):
    def testBasic(self):

        d = Deque()

        def handler(i):
            Tasklet.sleep(1.0)
            d.append(i)

        tp = TaskletPool()

        N = 10
        for i in range(N):
            tp.defer(handler, i)
 
        start = time.time()

        xs = []
        while True:
            xs.append(d.popleft(True, 30))
            if len(xs) == N:
                break
        
        end = time.time()
        
        #X workers taking 1 second to process N items = Z total proc time
        self.assertAlmostEqual(N / TaskletPool.INIT_WORKERS, end - start, places = 1)
        self.assertEquals(45, sum(xs))

class TestDeferredQueue(unittest.TestCase):
    def testDeferredQueue(self):
        
        d = DeferredQueue()
        
        def f(i):
            pass
        
        for i in range(10):    
            d.defer(f, i)
        
        Tasklet.sleep(1)

        for i in range(10):    
            d.defer(f, i)

        Tasklet.sleep(1)
        
        
class TestPrimitives(unittest.TestCase):        
    def testSemaphore(self):
        sema = Semaphore(4)
        self.assertEquals(True, sema.acquire())
        self.assertEquals(3, sema.count)        
        self.assertEquals(True, sema.acquire())
        self.assertEquals(2, sema.count)        
        self.assertEquals(True, sema.acquire())
        self.assertEquals(1, sema.count)        
        self.assertEquals(True, sema.acquire())
        self.assertEquals(0, sema.count)        
        self.assertEquals(False, sema.acquire(False))
        self.assertEquals(0, sema.count)        

        self.assertEquals(None, sema.release())
        self.assertEquals(1, sema.count)        
        self.assertEquals(None, sema.release())
        self.assertEquals(2, sema.count)        
        self.assertEquals(None, sema.release())
        self.assertEquals(3, sema.count)        
        self.assertEquals(None, sema.release())
        self.assertEquals(4, sema.count)        
        self.assertEquals(None, sema.release())
        self.assertEquals(5, sema.count) #possible to go beyond initial count... is this ok?        

        sema = Semaphore(4)
        xs = []

        def t(x):
            try:
                with sema:
                    Tasklet.sleep(1.0)
                    xs.append(x)
                return x
            except TimeoutError:
                pass

        start = time.time()
        for i in range(8):
            Tasklet.new(t)(i)

        join_result = Tasklet.join_children() 
        self.assertEquals(8, len(join_result))
        self.assertEquals(28, sum(xs))

        end = time.time()
        self.assertAlmostEqual(2.0, end - start, places = 1)
    
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
