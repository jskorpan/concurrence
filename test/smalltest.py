
import logging
import time
import sys
import inspect
import gc

from concurrence import _event, quit, dispatch, unittest, Tasklet, Channel, TimeoutError, TaskletError, JoinError, Message, TIMEOUT_NEVER

def smalltest():
    count = []

    def ival():
        #print "CALLED AT: %f from %s" % (time.time(), inspect.stack())
        count.append(1)

    #test non immediate
    ival_task = Tasklet.interval(1.0, ival, True)()

    try:
        Tasklet.join(ival_task, 3.0)
    except TimeoutError:
        #expect 3 counts, because interval started after 1 second
        if len(count) != 3:
            raise ValueError ("Len %d != 3" % len(count))

        print "We're all right!"   
    except:
        raise ValueError("expected timeout, got %s" % sys.exc_type)



    finally:
        ival_task.kill()
    print "DONE!"

    #test immediate
    def ival2():
        #print "CALLED AT: %f from %s" % (time.time(), inspect.stack())
        count.append(1)


    count = []
    ival_task = Tasklet.interval(1.0, ival2, False)()

    try:
        Tasklet.join(ival_task, 3.0)
    except TimeoutError:
        #expect 3 counts, because interval started after 1 second
        if len(count) != 2:
            raise ValueError ("Len %d != 2" % len(count))

        print "We're all right!"
    except:
        raise ValueError("expected timeout, got %s" % sys.exc_type)
    finally:
        ival_task.kill()
    print "DONE!"



    quit()


dispatch(smalltest)