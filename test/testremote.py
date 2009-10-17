from concurrence import unittest, Message, Tasklet, TimeoutError
from concurrence.remote import RemoteServer, RemoteTasklet, RemoteClient

import logging

class RemoteTest(unittest.TestCase):

    def testRemote(self):
        
        def server():
            remote_server = RemoteServer()
            server_endpoint = remote_server.serve(('localhost', 9081))
            remote_server.register('testing123')
            Tasklet.sleep(1.0)                
            print 'closing server' 
            server_endpoint.close()
            remote_server.close()
            print 'server closed'
            
        def client():
            try:
                remote_client = RemoteClient()
                remote_client.connect(('localhost', 9081))
                remote_client.lookup('testing123')
                remote_client.close()
                print 'client closed'
            except Exception:
                logging.exception("")
                self.fail("")
        
        server_task = Tasklet.new(server)()
        client_task = Tasklet.new(client)()

        Tasklet.join_children()
        
        del server_task
        del client_task
        print 'end'



        
if __name__ == '__main__':
    unittest.main(timeout = 5)
