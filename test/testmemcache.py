import os
import time

from concurrence import unittest, Tasklet
from concurrence.memcache.client import MemcacheResult, Memcache

MEMCACHE_IP = '127.0.0.1'

class MemcacheTest(unittest.TestCase):
    def setUp(self):
        for i in range(4):
            os.system('/usr/bin/memcached -m 10 -p %d -u nobody -l 127.0.0.1&' % (11211 + i))
    
    def tearDown(self):
        os.system('killall /usr/bin/memcached')
    
    def testNodeBasic(self):
        
        mc = Memcache()
        mc.set_servers([((MEMCACHE_IP, 11211), 100)])

        self.assertEquals(MemcacheResult.STORED, mc.set('test1', '12345'))
        self.assertEquals(MemcacheResult.STORED, mc.set('test2', '67890'))

        self.assertEquals('12345', mc.get('test1'))
        self.assertEquals('67890', mc.get('test2'))

        self.assertEquals(None, mc.get('test3'))
        self.assertEquals({'test1': '12345', 'test2': '67890'}, mc.get_multi(['test1', 'test2', 'test3']))

        #update test2
        mc.set('test2', 'hello world!')

        self.assertEquals({'test1': '12345', 'test2': 'hello world!'}, mc.get_multi(['test1', 'test2', 'test3']))
       
        #update to unicode type
        mc.set('test2', u'C\xe9line')
        self.assertEquals(u'C\xe9line', mc.get('test2'))

        #update to some other type
        mc.set('test2', {'piet': 'blaat', 10: 20})
        self.assertEquals({'piet': 'blaat', 10: 20}, mc.get('test2'))

        #test delete
        self.assertEquals(MemcacheResult.NOT_FOUND, mc.delete('test_del1'))
        self.assertEquals(MemcacheResult.STORED, mc.set('test_del1', 'hello'))
        self.assertEquals('hello', mc.get('test_del1'))
        self.assertEquals(MemcacheResult.DELETED, mc.delete('test_del1'))
        self.assertEquals(None, mc.get('test_del1'))
 
        #test add command
        mc.delete('add1')
        self.assertEquals(MemcacheResult.STORED, mc.add('add1', '11111'))
        self.assertEquals(MemcacheResult.NOT_STORED, mc.add('add1', '22222'))

        #test replace
        self.assertEquals(MemcacheResult.STORED, mc.set('replace1', '11111'))
        self.assertEquals(MemcacheResult.STORED, mc.replace('replace1', '11111'))
        self.assertEquals(MemcacheResult.STORED, mc.replace('replace1', '11111'))
        self.assertEquals(MemcacheResult.DELETED, mc.delete('replace1'))
        self.assertEquals(MemcacheResult.NOT_STORED, mc.replace('replace1', '11111'))


    def testMemcache(self):
        
        mc = Memcache()
        mc.set_servers([((MEMCACHE_IP, 11211), 100)])

        N = 10000

        with unittest.timer() as tmr:
            for i in range(N):
                mc.set('test2', 'hello world!')
        print 'single server single set keys/sec', tmr.sec(N)

    def testMemcacheMultiServer(self):
        
        mc = Memcache()
        mc.set_servers([((MEMCACHE_IP, 11211), 100), 
                        ((MEMCACHE_IP, 11212), 100), 
                        ((MEMCACHE_IP, 11213), 100), 
                        ((MEMCACHE_IP, 11214), 100)])

        N = 10000
        keys = ['test%d' % i for i in range(N)]

        with unittest.timer() as tmr:
            for i in range(N):
                self.assertEquals(MemcacheResult.STORED, mc.set(keys[i], 'hello world %d' % i))
        print 'multi server single set keys/sec', tmr.sec(N)

        with unittest.timer() as tmr:
            for i in range(N):
                self.assertEquals('hello world %d' % i, mc.get(keys[i]))
        print 'multi server single get keys/sec', tmr.sec(N)

        N = 10000
        for stride in [10,20,40]:
            with unittest.timer() as tmr:
                for i in range(0, N, stride):
                    result = mc.get_multi(keys[i:i+stride])
                    self.assertEquals(stride, len(result))
            print 'multi server multi get (%d) keys/sec' % stride, tmr.sec(N)

if __name__ == '__main__':
    unittest.main(timeout = 60)
