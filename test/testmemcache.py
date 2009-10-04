import os
import time

from concurrence import unittest, Tasklet
from concurrence.memcache.client import MemcacheResult, Memcache

MEMCACHE_IP = '127.0.0.1'

class TestMemcache(unittest.TestCase):
    def setUp(self):
        for i in range(4):
            os.system('/usr/bin/memcached -m 10 -p %d -u nobody -l 127.0.0.1&' % (11211 + i))
    
    def tearDown(self):
        os.system('killall /usr/bin/memcached')
    
    def testBasic(self):
        
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

    def testMultiClientMultiServer(self):
        
        N = 40 * 500
        keys = ['test%d' % i for i in range(N)]
        
        mc = Memcache()
        mc.set_servers([((MEMCACHE_IP, 11211), 100), 
                        ((MEMCACHE_IP, 11212), 100), 
                        ((MEMCACHE_IP, 11213), 100), 
                        ((MEMCACHE_IP, 11214), 100)])

        with unittest.timer() as tmr:
            for i in range(N):
                self.assertEquals(MemcacheResult.STORED, mc.set(keys[i], 'hello world %d' % i))
        print 'single client multi server single set keys/sec', tmr.sec(N)
        
        stride = 40
        def fetcher():
            for i in range(0, N, stride):
                result = mc.get_multi(keys[i:i+stride])
                self.assertEquals(stride, len(result))

        for nr_clients in [2,4,8,16]:
            with unittest.timer() as tmr:
                for i in range(nr_clients):
                    Tasklet.new(fetcher)()
                Tasklet.join_children()
            print 'multi client (%d), multi server multi get (%d) keys/sec' % (nr_clients, stride), tmr.sec(N * nr_clients)

    def testTextProtocol(self):
        from concurrence.io import Socket, BufferedStream
        from concurrence.memcache.client import MemcacheTextProtocol, RawCodec
        
        socket = Socket.connect((MEMCACHE_IP, 11211))
        stream = BufferedStream(socket)
        writer = stream.writer
        reader = stream.reader
        
        protocol = MemcacheTextProtocol(RawCodec())
        
        protocol.write_set(writer, 'hello', 'world')
        writer.flush()
        self.assertEquals(MemcacheResult.STORED, protocol.read_set(reader))
        
        N = 100
        for i in range(N):
            protocol.write_set(writer, 'test%d' % i, 'hello world %d' % i)
            writer.flush()
            self.assertEquals(MemcacheResult.STORED, protocol.read_set(reader))

        #single get
        for i in range(N):
            protocol.write_get(writer, ['test%d' % i])
            writer.flush()
            result = protocol.read_get(reader)
            self.assertEquals({'test%d' % i: 'hello world %d' % i}, result)

        #multi get
        for i in range(0, N, 10):
            keys = ['test%d' % x for x in range(i, i + 10)]
            protocol.write_get(writer, keys)
            writer.flush()
            result = protocol.read_get(reader)
            self.assertEquals(10, len(result))
            #self.assertEquals({'test%d' % i: 'hello world %d' % i}, result)
            
        #multi get pipeline, e.g. write N gets, but don't read out the results yet
        for i in range(0, N, 10):
            keys = ['test%d' % x for x in range(i, i + 10)]
            protocol.write_get(writer, keys)
            writer.flush()
        #now read the results
        for i in range(0, N, 10):
            result = protocol.read_get(reader)
            self.assertEquals(10, len(result))
            self.assertTrue(('test%d' % i) in result)

        #pipelined multiget with same set of keys
        protocol.write_get(writer, ['test2', 'test8', 'test9', 'test11', 'test23', 'test24', 'test29', 'test31', 'test34'])
        writer.flush()
        protocol.write_get(writer, ['test2', 'test8', 'test9', 'test11', 'test23', 'test24', 'test29', 'test31', 'test34'])
        writer.flush()
        result1 = protocol.read_get(reader)
        result2 = protocol.read_get(reader)
        self.assertEquals(result1, result2)
        
if __name__ == '__main__':
    unittest.main(timeout = 60)
    
