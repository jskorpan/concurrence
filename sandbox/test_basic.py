import socket

from concurrence import _event2 as event
from concurrence.io import Buffer, get_errno

from errno import EALREADY, EINPROGRESS, EWOULDBLOCK, ECONNRESET, ENOTCONN, ESHUTDOWN, EINTR, EISCONN, ENOENT, EAGAIN

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect(('127.0.0.1', 11211))
fd = s.fileno() 
#we are connected, turn to non-blockig mode
s.setblocking(0)
#print s.fileno()

STATE_WRITE_SET_REQUEST = 0
STATE_READ_SET_RESPONSE = 1
STATE_WAIT_SET_RESPONSE = 2

state = STATE_WRITE_SET_REQUEST 

N = 100000
#N = 1000
n = 0

buff = Buffer(1024)
 
def callback(flags):
    #print 'cb', flags
    if flags & event.EV_TIMEOUT:
        raise Exception("Timeout")
    global state
    global n
    while True:
        if state == STATE_WRITE_SET_REQUEST:
            buff.clear()
            key = 'piet%d' % n
            value = 'klaas%d' % n
            buff.write_bytes("%s %s %d 0 %d\r\n%s\r\n" % ('set', key, 0, len(value), value))
            buff.flip()
            written, remaining = buff.send(fd)
            if written < 0:
                raise Exception("TODO")
            if remaining > 0:
                raise Exception("TODO")
            state = STATE_READ_SET_RESPONSE
            buff.clear()
            read_event.add(1.0)
            return
        elif state == STATE_READ_SET_RESPONSE:
            read, remaining = buff.recv(fd)
            if read < 0:
                raise Exception("TODO")
            elif buff.position == 8:
                buff.flip() 
                #result = buff.read_line()
                #if result == 'STORED':
                if n < N:
                    n += 1
                    #print n
                    state = STATE_WRITE_SET_REQUEST
                else:
                    raise Exception("DONE")
                #else:
                #    raise Exception("TODO")
            else:
                raise Exception("TODO")
        else:
            raise Exception("UNKNOWN STATE")
        
              
read_event = event.event(fd, event.EV_READ, callback)
write_event = event.event(fd, event.EV_WRITE, callback)

import time

start = time.time()    

try:

    callback(0) #kick off!

    while event.loop():
        e, flags, fd = event.next()
        e.data(flags)

except:
    end = time.time()
    print '#set/sec', N / (end - start)
    raise

#with gil, using deque
#===============================================================================
# henk@henk-worktop:~/workspace/concurrence{speedup}$ stackless sandbox/test_basic.py 
# #set/sec 27512.9132082
# henk@henk-worktop:~/workspace/concurrence{speedup}$ stackless sandbox/test_basic.py 
# #set/sec 32166.8986723
# henk@henk-worktop:~/workspace/concurrence{speedup}$ stackless sandbox/test_basic.py 
# #set/sec 32139.9231288
# henk@henk-worktop:~/workspace/concurrence{speedup}$ stackless sandbox/test_basic.py 
# #set/sec 32263.7280136
# henk@henk-worktop:~/workspace/concurrence{speedup}$ stackless sandbox/test_basic.py 
# #set/sec 25581.622577
#===============================================================================
