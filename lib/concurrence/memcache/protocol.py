from concurrence.memcache import MemcacheError, MemcacheResult
from concurrence.memcache.codec import MemcacheCodec

class MemcacheProtocol(object):
    @classmethod
    def create(cls, type_):

        if isinstance(type_, MemcacheProtocol):
            return type_
        elif type_ == 'text':
            return MemcacheTextProtocol()
        else:
            raise MemcacheError("unknown protocol: %s" % type_)

class MemcacheTextProtocol(MemcacheProtocol):
    def __init__(self, codec = "default"):
        self.set_codec(codec)
        self._rcache = {}
        self._wcache = {}
        import inspect
        for name, member in inspect.getmembers(self):
            if name.startswith('read_'):
                self._rcache[name[5:]] = member
            elif name.startswith('write_'):
                self._wcache[name[6:]] = member

    def set_codec(self, codec):
        self._codec = MemcacheCodec.create(codec)

    def read(self, cmd, reader):
        return self._rcache[cmd](reader)

    def write(self, cmd, writer, args):
        return self._wcache[cmd](writer, *args)

    def _read_result(self, reader, value = None):
        response_line = reader.read_line()
        return MemcacheResult.get(response_line), value

    def write_version(self, writer):
        writer.write_bytes("version\r\n")

    def read_version(self, reader):
        response_line = reader.read_line()
        if response_line.startswith('VERSION'):
            return MemcacheResult.OK, response_line[8:].strip()
        else:
            return MemcacheResult.get(response_line), None

    def _write_storage(self, writer, cmd, key, value, expiration, flags):
        encoded_value, flags = self._codec.encode(value, flags)
        writer.write_bytes("%s %s %d %d %d\r\n%s\r\n" % (cmd, key, flags, expiration, len(encoded_value), encoded_value))

    def write_cas(self, writer, key, value, expiration, flags, cas_unique):
        encoded_value, flags = self._codec.encode(value, flags)
        writer.write_bytes("%s %s %d %d %d %d\r\n%s\r\n" % ("cas", key, flags, expiration, len(encoded_value), cas_unique, encoded_value))

    def read_cas(self, reader):
        return self._read_result(reader)

    def _write_incdec(self, writer, cmd, key, value):
        writer.write_bytes("%s %s %s\r\n" % (cmd, key, value))

    def _read_incdec(self, reader):
        response_line = reader.read_line()
        try:
            return MemcacheResult.OK, int(response_line)
        except ValueError:
            return MemcacheResult.get(response_line), None

    def write_incr(self, writer, key, value):
        self._write_incdec(writer, "incr", key, value)

    def read_incr(self, reader):
        return self._read_incdec(reader)

    def write_decr(self, writer, key, value):
        self._write_incdec(writer, "decr", key, value)

    def read_decr(self, reader):
        return self._read_incdec(reader)

    def write_get(self, writer, keys):
        writer.write_bytes("get %s\r\n" % " ".join(keys))

    def write_gets(self, writer, keys):
        writer.write_bytes("gets %s\r\n" % " ".join(keys))

    def read_get(self, reader, with_cas_unique = False):
        result = {}
        while True:
            response_line = reader.read_line()
            if response_line.startswith('VALUE'):
                response_fields = response_line.split(' ')
                key = response_fields[1]
                flags = int(response_fields[2])
                n = int(response_fields[3])
                if with_cas_unique:
                    cas_unique = int(response_fields[4])
                encoded_value = reader.read_bytes(n)
                reader.read_line() #\r\n
                if with_cas_unique:
                    result[key] = (self._codec.decode(flags, encoded_value), cas_unique)
                else:
                    result[key] = self._codec.decode(flags, encoded_value)
            elif response_line == 'END':
                return MemcacheResult.OK, result
            else:
                return MemcacheResult.get(response_line), {}

    def read_gets(self, reader):
        return self.read_get(reader, with_cas_unique = True)

    def write_delete(self, writer, key, expiration):
        writer.write_bytes("delete %s %d\r\n" % (key, expiration))

    def read_delete(self, reader):
        return self._read_result(reader)

    def write_set(self, writer, key, value, expiration, flags):
        return self._write_storage(writer, "set", key, value, expiration, flags)

    def read_set(self, reader):
        return self._read_result(reader)

    def write_add(self, writer, key, value, expiration, flags):
        return self._write_storage(writer, "add", key, value, expiration, flags)

    def read_add(self, reader):
        return self._read_result(reader)

    def write_replace(self, writer, key, value, expiration, flags):
        return self._write_storage(writer, "replace", key, value, expiration, flags)

    def read_replace(self, reader):
        return self._read_result(reader)

    def write_append(self, writer, key, value, expiration, flags):
        return self._write_storage(writer, "append", key, value, expiration, flags)

    def read_append(self, reader):
        return self._read_result(reader)

    def write_prepend(self, writer, key, value, expiration, flags):
        return self._write_storage(writer, "prepend", key, value, expiration, flags)

    def read_prepend(self, reader):
        return self._read_result(reader)
