#===============================================================================
# from collections import deque
# 
# d = deque()
# 
# N = 10000000
# 
# for i in range(N):
#    d.append(i)
#    
# import time
# start = time.time()    
# 
# while d:
#    d.popleft()
# 
# end = time.time()
# print '#set/sec', N / (end - start)
#    
#===============================================================================

from concurrence._event2 import f

def g(a):
    return a
 

N = 10000000

import time
start = time.time()    
for i in xrange(N):
    g(i) 
end = time.time()
print '#/sec', N / (end - start)

import time
start = time.time()    
for i in xrange(N):
    f(i) 
end = time.time()
print '#/sec', N / (end - start)

