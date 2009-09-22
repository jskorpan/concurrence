import stackless

from concurrence import _event

def heartbeat(_):
    heartbeat_ev.add(1.0)

heartbeat_ev = _event.event(heartbeat, 0)
heartbeat_ev.add(1.0)

def dispatch():
    while True:
        triggered = _event.loop()
        while triggered:
            callback, evtype = triggered.popleft()
            callback(evtype)

if __name__ == '__main__':
    dispatch()

