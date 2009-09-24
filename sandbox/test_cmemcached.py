
N = 1000000

def test_cmemcached():
    import cmemcached    
    mc = cmemcached.Client(["127.0.0.1:11211"])
    for i in range(N):
        mc.set('piet%d' % i, 'klaas%d' % i)

if __name__ == '__main__':
    test_cmemcached()

