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

    def __init__(self):
        self._queue = Deque()
        self._workers = []
        self._workers.append(Tasklet.new(self._worker, daemon = True)())
        self._adjuster = Tasklet.interval(0.25, self._adjust, daemon = True)()
        self._queue_len = 0.0

    def _adjust(self):  
        gamma = 0.995
        self._queue_len = (gamma * self._queue_len) + ((1.0 - gamma) * len(self._queue))
        x = int(self._queue_len) - len(self._workers)
        if x > 0:
            for _ in range(x):
                self._workers.append(Tasklet.new(self._worker, daemon = True)())
            self.log.debug('adjusted #worker tasks, now: %s', len(self._workers))

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
    




        

