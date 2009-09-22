from concurrence import Tasklet, dispatch, quit
from concurrence.memcache.client import MemcacheConnection

import logging

N = 10000

def test_cmemcached():
    import cmemcached    
    mc = cmemcached.Client(["127.0.0.1:11211"])
    for i in range(N):
        mc.set('piet', 'klaas')
        mc.get('piet')

def test_concurrence_memcache():
    mc = MemcacheConnection(('127.0.0.1', 11211))
    for i in range(N):
        mc.set('piet', 'klaas')
        mc.get('piet')
    quit()

if __name__ == '__main__':
    logging.basicConfig()
    #test_cmemcached()
    dispatch(test_concurrence_memcache)

