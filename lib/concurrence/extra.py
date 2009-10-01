import logging

from concurrence.core import Tasklet, Channel, Deque

class Lock(object):
    def __init__(self):
        self._locked = False
        self._owner = None
        self._channel = Channel()

    def is_locked(self):
        return self._locked

    def acquire(self, blocking = True, timeout = -2):
        if not self._locked:
            #print '1'
            self._locked = True
            return True
        else:
            if not blocking:
                #print '2'
                return False
            else:
                #print '3'
                return self._channel.receive(timeout) 

    def release(self):
        assert self._locked
        if self._channel.has_receiver():
            #stay locked, unblock 1 receiver
            self._channel.send(True)
        else:
            self._locked = False       

    def __enter__(self):
        self.acquire()
        return self
     
    def __exit__(self, type, value, traceback):
        self.release()

class TaskletPool(object):
    log = logging.getLogger('TaskletPool')

    def __init__(self, min_worker_count):
        self._queue = Deque()
        for i in range(min_worker_count):
            Tasklet.new(self._worker, daemon = True)()

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

_task_pool = TaskletPool(10)
        
defer = _task_pool.defer
    




        

