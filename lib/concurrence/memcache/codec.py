import cPickle as pickle

class Codec(object):
    def decode(self, flags, encoded_value):
        assert False, "implement"

    def encode(self, value):
        assert False, "implement"

class DefaultCodec(Codec):
    _FLAG_PICKLE = 1<<0
    _FLAG_INTEGER = 1<<1
    _FLAG_LONG = 1<<2
    _FLAG_UNICODE = 1<<3

    def decode(self, flags, encoded_value):
        if flags & self._FLAG_INTEGER:
            return int(encoded_value)
        elif flags & self._FLAG_LONG:
            return long(encoded_value)
        elif flags & self._FLAG_UNICODE:
            return encoded_value.decode('utf-8')
        elif flags & self._FLAG_PICKLE:
            return pickle.loads(encoded_value)
        else:
            return encoded_value

    def encode(self, value):
        flags = 0
        if isinstance(value, str):
            encoded_value = value
        elif isinstance(value, int):
            flags |= self._FLAG_INTEGER
            encoded_value = str(value)
        elif isinstance(value, long):
            flags |= self._FLAG_LONG
            encoded_value = str(value)
        elif isinstance(value, unicode):
            flags |= self._FLAG_UNICODE
            encoded_value = value.encode('utf-8')
        else:
            flags |= self._FLAG_PICKLE            
            encoded_value = pickle.dumps(value, -1)
        return encoded_value, flags

class RawCodec(Codec):
    def decode(self, flags, encoded_value):
        return encoded_value

    def encode(self, value):
        return str(value), 0

