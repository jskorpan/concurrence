import cPickle as pickle

class Codec(object):
    def decode(self, flags, encoded_value):
        assert False, "implement"

    def encode(self, value):
        assert False, "implement"

class DefaultCodec(Codec):
    def decode(self, flags, encoded_value):
        return pickle.loads(encoded_value)

    def encode(self, value):
        return pickle.dumps(value, -1), 0

class RawCodec(Codec):
    def decode(self, flags, encoded_value):
        return encoded_value

    def encode(self, value):
        return str(value), 0

