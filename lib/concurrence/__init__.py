# Copyright (C) 2009, Hyves (Startphone Ltd.)
#
# This module is part of the Concurrence Framework and is released under
# the New BSD License: http://www.opensource.org/licenses/bsd-license.php
__version__ = '0.3.1' #remember to update setup.py
__version_info__ = tuple([ int(num) for num in __version__.split('.')])

from concurrence.core import dispatch, quit, disable_threading, get_version_info
from concurrence.core import Channel, Tasklet, Message, Deque, FileDescriptorEvent, SignalEvent, TimeoutEvent
from concurrence.core import TimeoutError, TaskletError, JoinError
from concurrence.extra import TaskletPool, DeferredQueue, Lock, Semaphore
from concurrence.local import TaskLocal, TaskInstance

import concurrence._unittest as unittest

try:
    import json
except:
    try:
        import simplejson as json
    except:
        import logging
        logging.exception("could not import json library!', pls install simplejson or use python 2.6+")

