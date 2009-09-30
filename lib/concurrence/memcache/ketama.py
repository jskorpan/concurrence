import math
import hashlib
import bisect
    
x = """10.0.1.1:11211  600
10.0.1.2:11211  300
10.0.1.3:11211  200
10.0.1.4:11211  350
10.0.1.5:11211  1000
10.0.1.6:11211  800
10.0.1.7:11211  950
10.0.1.8:11211  100
"""    

def parse_servers(x):
    y = x.splitlines()
    assert len(y) == 8
    y = [z.split() for z in y]
    assert len(y) == 8
    y = [(tuple(z[0].split(':')), int(z[1])) for z in y]
    assert len(y) == 8
    y = [((z[0][0], int(z[0][1])), z[1]) for z in y]
    return y

def get_server(key, continuum):
    #hash the key to a point
    point = long(hashlib.md5(str(key)).hexdigest()[0:8], 16)
    i = bisect.bisect_right(continuum, (point, ()))
    if i < len(continuum):
        return continuum[i][1]
    else:
        return continuum[0][1]
     
def build_continuum(servers):
    continuum = {}
    memory = sum([s[1] for s in servers]) #total weight of servers (a.k.a. memory)
    server_count = len(servers) 
    
    for server in servers:
        pct = float(server[1]) / memory #pct of memory of this server
        ks = int(math.floor(pct * 40.0 * server_count))
        for k in range(ks):
            # max 40 hashes, 4 numbers per hash = max 160 points per server */
            ss = "%s:%s-%d" % (server[0][0], server[0][1], k)
            digest = hashlib.md5(ss).hexdigest()            
            for h in range(4):
                point = long(digest[h * 8: h * 8 + 8], 16)
                if not point in continuum:
                    continuum[point] = server[0]
                else:
                    assert False, "point collission while building continuum"
    #continuum.sort()
    #return continuum
    return sorted(continuum.items())

def rand_string():
    import random
    import string
    return ''.join([random.choice(string.letters) for i in range(32)])
                    
if __name__ == '__main__':
    #print create_continuum([(('127.0.0.1', 11211), ])
    servers = parse_servers(x)
    continuum = build_continuum(servers)
    for c in continuum:
        print c
    print
    print get_server('henk p', continuum)
    for i in range(100):
        print get_server(rand_string(), continuum)