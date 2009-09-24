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

cdef class __event
cdef struct __list

ctypedef void (*event_handler)(int fd, short event, void* arg)

cdef extern from "string.h":
    char *strerror(int errno)

cdef extern from "errno.h":
    int errno

cdef extern from "event.h":
    struct timeval:
        unsigned int tv_sec
        unsigned int tv_usec
    
    struct event_t "event":
        int   ev_fd
        int   ev_flags
        void *ev_arg

    void event_init() nogil 
    char *event_get_version() nogil
    char *event_get_method() nogil
    void event_set(event_t *ev, int fd, short event, event_handler handler, void *arg) nogil
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

cdef struct __list:
    void *event
    short flags
    int fd
    __list *next

cdef __list* head
head = NULL

cdef void __event_handler(int fd, short flags, void* arg) nogil:
    cdef __list *tmp
    cdef __list *trig
    trig = <__list*>arg
    trig.flags = flags
    trig.fd = fd
    global head
    if head == NULL:
        head = trig
        head.next = NULL
    else:
        tmp = head
        head = trig
        head.next = tmp

cdef class __event:
    cdef public object data

    cdef event_t ev
    cdef __list trig
    
    def __init__(self, object data):
        self.data = data
        self.trig.event = <void *>self
                
    def set(self, int fd, short event): 
        event_set(&self.ev, fd, event, __event_handler, <void *>&self.trig)

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

    def pending(self, int event):
        """Return 1 if the event is scheduled to run, or else 0."""
        return event_pending(&self.ev, event, NULL)
    
    def delete(self):
        if event_del(&self.ev) == -1:
            raise EventError("could not delete event")
    
    def __repr__(self):
        return '<_event id=0x%x, flags=0x%x, data=%s>' % (id(self), self.ev.ev_flags, self.data)

def event(fd, event, data):
    e = __event(data)
    e.set(fd, event)
    return e 

def version():
    return event_get_version()

def method():
    return event_get_method()

_next = None

def next():
    return _next

def loop():
    cdef __list* tmp
    cdef int result

    global head
    if head == NULL:
        with nogil:
            result = event_loop(EVLOOP_ONCE)
        if result == -1:
            raise EventError("error in event_loop")

    global _next
    if head == NULL:
        _next = None
        return False
    else:
        _next = (<__event>head.event, head.flags, head.fd)
        head = head.next
        return True
    
#init libevent
event_init()

