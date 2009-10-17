from concurrence.core import Tasklet, Channel, Deque

import logging
from collections import deque

class Semaphore(object):
    def __init__(self, count):
        self._count = count
        self._channel = Channel()

    @property
    def count(self):
        return self._count

    def acquire(self, blocking = True, timeout = -2):
        if self._count > 0:
            self._count -= 1
            return True
        else:
            if not blocking: 
                return False
            else:
                return self._channel.receive(timeout)

    def release(self):
        if self._channel.has_receiver():
            self._channel.send(True)
        else:
            self._count += 1

    def __enter__(self):
        self.acquire()
        return self
     
    def __exit__(self, type, value, traceback):
        self.release()

class Lock(Semaphore):
    def __init__(self):
        super(Lock, self).__init__(1)

    def is_locked(self):
        return self.count == 0

class TaskletPool(object):
    log = logging.getLogger('TaskletPool')

    GAMMA = 0.995
    TRESHOLD = 2.0

    def __init__(self):
        self._queue = Deque()
        self._workers = []
        #self._add_worker()
        #self._add_worker()
        #self._adjuster = Tasklet.interval(1.0, self._adjust, daemon = True)()
        self._queue_len = 0.0

    def _add_worker(self):
        self._workers.append(Tasklet.new(self._worker, daemon = True)())
        self.log.debug('addded worker, #now: %s', len(self._workers))

    def _adjust(self):
        self._queue_len = (self.GAMMA * self._queue_len) + ((1.0 - self.GAMMA) * len(self._queue))
        x = self._queue_len / len(self._workers)
        if x > self.TRESHOLD:
            self._add_worker()

    def _worker(self):
        while True:
            try:
                f, args, kwargs = self._queue.popleft(True, -1)
                f(*args, **kwargs)
            except TaskletExit:
                raise
            except:
                self.log.exception("in taskpool worker")
                Tasklet.sleep(1.0)

    def defer(self, f, *args, **kwargs):
        self._queue.append((f, args, kwargs))

_task_pool = TaskletPool()
        
defer = _task_pool.defer
    
class DeferredQueue(object):
    log = logging.getLogger('DeferredQueue')
    
    def __init__(self):
        self._queue = deque()
        self._working = False
        
    def _pump(self):
        try:
            while self._queue:
                try:
                    f, args, kwargs = self._queue.popleft()
                    f(*args, **kwargs)
                except TaskletExit:
                    raise
                except:
                    self.log.exception("in deferred queue")
        finally:
            self._working = False
            
    def defer(self, f, *args, **kwargs):
        self._queue.append((f, args, kwargs))
        if not self._working:
            self._working = True
            _task_pool.defer(self._pump)
    



        

