from concurrence.memcache import ketama

class MemcacheBehaviour(object):
    @classmethod
    def create(cls, type_):
        if type_ == "modulo":
            return MemcacheModuloBehaviour()
        elif type_ == "ketama":
            return MemcacheKetamaBehaviour()

class MemcacheModuloBehaviour(MemcacheBehaviour):
    def __init__(self):
        pass

    def set_servers(self, servers):
        self._servers = servers

    def key_to_addr(self, key):
        return self._servers[hash(key) % len(self._servers)]

class MemcacheKetamaBehaviour(MemcacheBehaviour):
    def __init__(self):
        self._continuum = None

    def set_servers(self, servers):
        self._continuum = ketama.build_continuum(servers)

    def key_to_addr(self, key):
        return ketama.get_server(key, self._continuum)


