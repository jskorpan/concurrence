import os

from concurrence import unittest, Tasklet
from concurrence.memcache.client import MemcacheConnection, MemcacheResult

class MemcacheTest(unittest.TestCase):
    def testNodeBasic(self):
        
        node = MemcacheConnection(('127.0.0.1', 11211))

        self.assertEquals(MemcacheResult.STORED, node.set('test1', '12345'))
        self.assertEquals(MemcacheResult.STORED, node.set('test2', '67890'))

        self.assertEquals('12345', node.get('test1'))
        self.assertEquals('67890', node.get('test2'))

        self.assertEquals(None, node.get('test3'))
        self.assertEquals({'test1': '12345', 'test2': '67890'}, node.multi_get(['test1', 'test2', 'test3']))

        #update test2
        node.set('test2', 'hello world!')

        self.assertEquals({'test1': '12345', 'test2': 'hello world!'}, node.multi_get(['test1', 'test2', 'test3']))
       
        #update to unicode type
        node.set('test2', u'C\xe9line')
        self.assertEquals(u'C\xe9line', node.get('test2'))

        #update to some other type
        node.set('test2', {'piet': 'blaat', 10: 20})
        self.assertEquals({'piet': 'blaat', 10: 20}, node.get('test2'))

        #test delete
        self.assertEquals(MemcacheResult.NOT_FOUND, node.delete('test_del1'))
        self.assertEquals(MemcacheResult.STORED, node.set('test_del1', 'hello'))
        self.assertEquals('hello', node.get('test_del1'))
        self.assertEquals(MemcacheResult.DELETED, node.delete('test_del1'))
        self.assertEquals(None, node.get('test_del1'))
 
        #test add command
        node.delete('add1')
        self.assertEquals(MemcacheResult.STORED, node.add('add1', '11111'))
        self.assertEquals(MemcacheResult.NOT_STORED, node.add('add1', '22222'))

        #test replace
        self.assertEquals(MemcacheResult.STORED, node.set('replace1', '11111'))
        self.assertEquals(MemcacheResult.STORED, node.replace('replace1', '11111'))
        self.assertEquals(MemcacheResult.STORED, node.replace('replace1', '11111'))
        self.assertEquals(MemcacheResult.DELETED, node.delete('replace1'))
        self.assertEquals(MemcacheResult.NOT_STORED, node.replace('replace1', '11111'))

        node.close()
        
if __name__ == '__main__':
    unittest.main(timeout = 60)
