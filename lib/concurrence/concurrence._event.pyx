#
# event.pyx
#
# libevent Python bindings
#
# Copyright (c) 2004 Dug Song <dugsong@monkey.org>
# Copyright (c) 2003 Martin Murray <murrayma@citi.umich.edu>
#
# $Id: event.pyx,v 1.12 2005/09/12 03:16:15 dugsong Exp $

"""event library

This module provides a mechanism to execute a function when a
specific event on a file handle, file descriptor, or signal occurs,
or after a given time has passed.
"""

__author__ = ( 'Dug Song <dugsong@monkey.org>',
               'Martin Murray <mmurray@monkey.org>' )
__copyright__ = ( 'Copyright (c) 2004 Dug Song',
                  'Copyright (c) 2003 Martin Murray' )
__license__ = 'BSD'
__url__ = 'http://monkey.org/~dugsong/pyevent/'
__version__ = '0.3'

import collections

# Added by JOTA
import inspect


debugLog = []

cdef class __event
cdef struct __list

ctypedef void (*event_handler)(int fd, short event_type, void* arg)

IF UNAME_SYSNAME == "Windows":
    cdef extern from "winsock2.h":
        struct timeval:
            unsigned int tv_sec
            unsigned int tv_usec

    cdef extern from "win32.h":
        void winsock_init()

ELSE:
    cdef extern from "event.h":
        struct timeval:
            unsigned int tv_sec
            unsigned int tv_usec

cdef extern from "string.h":
    char *strerror(int errno)

cdef extern from "errno.h":
    int errno

cdef extern from "event.h":

    struct event_t "event":
        int   ev_fd
        int   ev_flags
        void *ev_arg

    void event_init() nogil
    char *event_get_version() nogil
    char *event_get_method() nogil
    void event_set(event_t *ev, int fd, short event_type, event_handler handler, void *arg) nogil
    int  event_add(event_t *ev, timeval *tv) nogil
    int  event_del(event_t *ev) nogil
    int  event_loop(int flags) nogil
    int  event_pending(event_t *ev, short, timeval *tv) nogil

    void evtimer_set(event_t *ev, event_handler handler, void *arg) nogil

    int EVLOOP_ONCE
    int EVLOOP_NONBLOCK

EV_TIMEOUT      = 0x01
EV_READ         = 0x02
EV_WRITE        = 0x04
EV_SIGNAL       = 0x08
EV_PERSIST      = 0x10

class EventError(Exception):
    def __init__(self, msg):
        Exception.__init__(self, msg + ": " + strerror(errno))

#keep a singly-linked list of events that are triggered during 1 call to 'loop'
#we will append at the end, and our client will read from the front
#therefore we keep 2 pointers to the head and tail of the list to easily
#provide these FIFO operations
cdef struct __list:
    void *event
    short flags
    int fd
    __list *next

cdef __list* head
cdef __list* tail
head = NULL
tail = NULL

cdef void __event_handler(int fd, short flags, void* arg):
    cdef __list *tmp
    cdef __list *trig
    trig = <__list*>arg
    trig.flags = flags
    trig.fd = fd
    global head
    global tail

    if head == NULL:
        trig.next = NULL
        head = trig
        tail = trig
    else:
        trig.next = NULL
        tail.next = trig
        tail = trig




cdef class __event:
    cdef public object data

    cdef event_t ev
    cdef __list trig
    cdef public object deleted

    def __init__(self, object data):
        self.data = data
        self.trig.event = <void *>self
        self.trig.flags = 0
        self.trig.fd = 0
        self.trig.next = NULL

    def _set(self, int fd, short event_type):
        event_set(&self.ev, fd, event_type, __event_handler, <void *>&self.trig)

    def add(self, float timeout = -1):
        """Add event to be executed after an optional timeout."""
        cdef timeval tv
        if timeout >= 0.0:
            tv.tv_sec = <long>timeout
            tv.tv_usec = <long>((timeout - <float>tv.tv_sec) * 1000000.0)

            if event_add(&self.ev, &tv) == -1:
                raise EventError("could not add event")
        else:
            if event_add(&self.ev, NULL) == -1:
                raise EventError("could not add event")

    def pending(self, int event_type):
        """Return 1 if the event is scheduled to run, or else 0."""
        return event_pending(&self.ev, event_type, NULL)

    def delete(self):
        #NOTE: JOTA: Events seems to be deleted multiple times here, performance?

        #debugLog.append ("Deleting event %s" % (inspect.stack()))

        if event_del(&self.ev) == -1:
            raise EventError("could not delete event")

    def __dealloc__(self):
        self.delete()

    def __repr__(self):
        return '<_event id=0x%x, flags=0x%x, data=%s>' % (id(self), self.ev.ev_flags, self.data)

def event(fd, event_type, data):
    e = __event(data)
    e._set(fd, event_type)
    return e

def version():
    return event_get_version()

def method():
    return event_get_method()

def has_next():
    global head
    return head != NULL

def next():
    global head
    if head == NULL:
        return None
    else:
        triggered = (<__event>head.event, head.flags, head.fd)
        head = head.next
        return triggered

def loop():
    cdef int result
    global head
    if head == NULL:
        with nogil:
            result = event_loop(EVLOOP_ONCE)
        if result == -1:
            raise EventError("error in event_loop")
    else:
        raise EventError("can only enter loop when all previous events have been read")

    return head != NULL

#init libevent
IF UNAME_SYSNAME == "Windows":
    winsock_init()

event_init()

