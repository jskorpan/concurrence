import logging

from concurrence.core import Tasklet, Deque

class TaskletPool(object):
    log = logging.getLogger('TaskletPool')

    def __init__(self, inital_worker_count):
        self._queue = Deque()
        for i in range(inital_worker_count):
            Tasklet.new(self._worker)()

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
        
        
