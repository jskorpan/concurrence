from __future__ import with_statement

import os
import time
import logging

from concurrence import unittest, Tasklet
from concurrence.memcache import MemcacheResultCode, Memcache, MemcacheTCPConnection

MEMCACHE_IP = '127.0.0.1'

MEMCACHED_PATHS = ['/opt/memcached/bin/memcached',
                   '/usr/bin/memcached',
                   '/opt/local/bin/memcached']

MEMCACHED_BIN = None
for path in MEMCACHED_PATHS:
    if os.path.exists(path):
        MEMCACHED_BIN = path
        break
assert MEMCACHED_BIN is not None, "could not find memcached daemon binary"

#TODO check for memcached version before testing cas/gets commands

class TestMemcache(unittest.TestCase):
    log = logging.getLogger("TestMemcache")

    def setUp(self):
        self.log.debug("using memcached daemon: %s", MEMCACHED_BIN)

        for i in range(4):
            cmd = '%s -m 10 -p %d -u nobody -l 127.0.0.1&' % (MEMCACHED_BIN, 11211 + i)
            self.log.debug(cmd)
            os.system(cmd)

        Tasklet.sleep(1.0) #should be enough for memcached to get up and running

    def tearDown(self):
        cmd = 'killall %s' % MEMCACHED_BIN
        self.log.debug(cmd)
        os.system(cmd)

        Tasklet.sleep(1.0) #should be enough for memcached to go down

    def sharedTestBasic(self, mc):

        self.assertEquals(MemcacheResultCode.STORED, mc.set('test1', '12345'))
        self.assertEquals(MemcacheResultCode.STORED, mc.set('test2', '67890'))

        self.assertEquals('12345', mc.get('test1'))
        self.assertEquals('67890', mc.get('test2'))

        self.assertEquals(None, mc.get('test3'))
        self.assertEquals({'test1': '12345', 'test2': '67890'}, mc.get_multi(['test1', 'test2', 'test3']))

        #update test2
        mc.set('test2', 'hello world!')

        self.assertEquals({'test1': '12345', 'test2': 'hello world!'}, mc.get_multi(['test1', 'test2', 'test3']))

        #update to int type
        mc.set('test2', 10)
        self.assertEquals(10, mc.get('test2'))
        self.assertEquals(int, type(mc.get('test2')))

        #update to long type
        mc.set('test2', 10L)
        self.assertEquals(10L, mc.get('test2'))
        self.assertEquals(long, type(mc.get('test2')))

        #update to string type
        mc.set('test2', 'blaat')
        self.assertEquals('blaat', mc.get('test2'))
        self.assertEquals(str, type(mc.get('test2')))

        #update to unicode type
        mc.set('test2', u'C\xe9line')
        self.assertEquals(u'C\xe9line', mc.get('test2'))
        self.assertEquals(unicode, type(mc.get('test2')))

        #update to some other type
        mc.set('test2', {'piet': 'blaat', 10: 20})
        self.assertEquals({'piet': 'blaat', 10: 20}, mc.get('test2'))

        #test delete
        self.assertEquals(MemcacheResultCode.NOT_FOUND, mc.delete('test_del1'))
        self.assertEquals(MemcacheResultCode.STORED, mc.set('test_del1', 'hello'))
        self.assertEquals('hello', mc.get('test_del1'))
        self.assertEquals(MemcacheResultCode.DELETED, mc.delete('test_del1'))
        self.assertEquals(None, mc.get('test_del1'))

        #test add command
        mc.delete('add1')
        self.assertEquals(MemcacheResultCode.STORED, mc.add('add1', '11111'))
        self.assertEquals(MemcacheResultCode.NOT_STORED, mc.add('add1', '22222'))

        #test replace
        self.assertEquals(MemcacheResultCode.STORED, mc.set('replace1', '11111'))
        self.assertEquals(MemcacheResultCode.STORED, mc.replace('replace1', '11111'))
        self.assertEquals(MemcacheResultCode.STORED, mc.replace('replace1', '11111'))
        self.assertEquals(MemcacheResultCode.DELETED, mc.delete('replace1'))
        self.assertEquals(MemcacheResultCode.NOT_STORED, mc.replace('replace1', '11111'))

        #test cas/gets
        self.assertEquals(MemcacheResultCode.NOT_FOUND, mc.cas('cas_test1', 'blaat', 12345))
        self.assertEquals(MemcacheResultCode.STORED, mc.set('cas_test1', 'blaat'))
        value, cas_unique = mc.gets('cas_test1')
        self.assertEquals('blaat', value)
        self.assertEquals(MemcacheResultCode.STORED, mc.cas('cas_test1', 'blaat2', cas_unique))
        self.assertEquals(MemcacheResultCode.EXISTS, mc.cas('cas_test1', 'blaat2', cas_unique))
        value, cas_unique = mc.gets('cas_test1')
        self.assertEquals('blaat2', value)
        self.assertEquals(MemcacheResultCode.STORED, mc.cas('cas_test1', 'blaat3', cas_unique))
        self.assertEquals(MemcacheResultCode.STORED, mc.set('cas_test2', 'blaat4'))

        result = mc.gets_multi(['cas_test1', 'cas_test2'])
        self.assertTrue('cas_test1' in result)
        self.assertTrue('cas_test2' in result)
        self.assertEquals('blaat3', result['cas_test1'][0])
        self.assertEquals('blaat4', result['cas_test2'][0])

    def testBasicSingle(self):
        mc = MemcacheTCPConnection()
        mc.connect((MEMCACHE_IP, 11211))

        self.sharedTestBasic(mc)

    def testBasic(self):

        mc = Memcache()
        mc.set_servers([((MEMCACHE_IP, 11211), 100)])

        self.sharedTestBasic(mc)

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
                self.assertEquals(MemcacheResultCode.STORED, mc.set(keys[i], 'hello world %d' % i))
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

        N = 40 * 100
        keys = ['test%d' % i for i in range(N)]

        mc = Memcache()
        mc.set_servers([((MEMCACHE_IP, 11211), 100),
                        ((MEMCACHE_IP, 11212), 100),
                        ((MEMCACHE_IP, 11213), 100),
                        ((MEMCACHE_IP, 11214), 100)])

        with unittest.timer() as tmr:
            for i in range(N):
                self.assertEquals(MemcacheResultCode.STORED, mc.set(keys[i], 'hello world %d' % i))
        print 'single client multi server single set keys/sec', tmr.sec(N)

        stride = 40
        def fetcher():
            for i in range(0, N, stride):
                result = mc.get_multi(keys[i:i+stride])
                self.assertEquals(stride, len(result))

        for nr_clients in [2,4,8,16,32,64,128]:
            with unittest.timer() as tmr:
                for i in range(nr_clients):
                    Tasklet.new(fetcher)()
                Tasklet.join_children()
            print 'multi client (%d), multi server multi get (%d) keys/sec' % (nr_clients, stride), tmr.sec(N * nr_clients)

    def testTextProtocol(self):
        from concurrence.io import Socket, BufferedStream
        from concurrence.memcache.client import MemcacheTextProtocol
        from concurrence.memcache.codec import RawCodec

        socket = Socket.connect((MEMCACHE_IP, 11211))
        stream = BufferedStream(socket)
        writer = stream.writer
        reader = stream.reader

        protocol = MemcacheTextProtocol("raw")

        protocol.write_set(writer, 'hello', 'world')
        writer.flush()
        self.assertEquals(MemcacheResultCode.STORED, protocol.read_set(reader))

        N = 100
        for i in range(N):
            protocol.write_set(writer, 'test%d' % i, 'hello world %d' % i)
            writer.flush()
            self.assertEquals(MemcacheResultCode.STORED, protocol.read_set(reader))

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

