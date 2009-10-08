# Copyright (C) 2009, Hyves (Startphone Ltd.)
#
# This module is part of the Concurrence Framework and is released under
# the New BSD License: http://www.opensource.org/licenses/bsd-license.php

from concurrence.io import IOStream, Buffer, BufferOverflowError, BufferUnderflowError, BufferInvalidArgumentError


class BufferedReader(object):
    def __init__(self, stream, buffer):
        assert stream is None or isinstance(stream, IOStream)
        self.stream = stream
        self.buffer = buffer
        #assume no reading from underlying stream was done, so make sure buffer reflects this:
        self.buffer.position = 0
        self.buffer.limit = 0

    def file(self):
        return CompatibleFile(self, None)

    def clear(self):
        self.buffer.clear()

    def _read_more(self):
        #any partially read data will be put in front, otherwise normal clear:
        self.buffer.compact()
        if not self.stream.read(self.buffer, -2): 
            raise EOFError("while reading")
        self.buffer.flip() #prepare to read from buffer
        
    def read_lines(self):
        """note that it cant read line accross buffer"""
        if self.buffer.remaining == 0:
            self._read_more()
        while True:
            try:
                yield self.buffer.read_line()
            except BufferUnderflowError:
                self._read_more()
        
    def read_line(self):
        """note that it cant read line accross buffer"""
        if self.buffer.remaining == 0:
            self._read_more()
        while True:
            try:
                return self.buffer.read_line()
            except BufferUnderflowError:
                self._read_more()
                
    def read_bytes(self, n):
        """read exactly n bytes from stream"""
        buffer = self.buffer
        s = []
        while n > 0:
            r = buffer.remaining 
            if r > 0:
                s.append(buffer.read_bytes(min(n, r)))
                n -= r 
            else:
                self._read_more()
                
        return ''.join(s)

    def read_short(self):
        if self.buffer.remaining == 0:
            self._read_more()
        while True:
            try:
                return self.buffer.read_short()
            except BufferUnderflowError:
                self._read_more()
                
class BufferedWriter(object):
    def __init__(self, stream, buffer):
        assert stream is None or isinstance(stream, IOStream)
        self.stream = stream
        self.buffer = buffer 
    
    def file(self):
        return CompatibleFile(None, self)

    def clear(self):
        self.buffer.clear()

    def write_bytes(self, s):
        assert type(s) == str, "arg must be a str, got: %s" % type(s)
        try:
            self.buffer.write_bytes(s)
        except BufferOverflowError:
            #we need to send it in parts, flushing as we go
            while s:
                r = self.buffer.remaining
                part, s = s[:r], s[r:]
                self.buffer.write_bytes(part)
                self.flush()    
 
    def write_byte(self, ch):
        assert type(ch) == int, "ch arg must be int"
        while True:
            try:
                self.buffer.write_byte(ch)
                return
            except BufferOverflowError:
                self.flush()
       
    def write_short(self, i):
        while True:
            try:
                self.buffer.write_short(i)
                return
            except BufferOverflowError:
                self.flush()
            
    def flush(self):
        self.buffer.flip()
        while self.buffer.remaining:
            if not self.stream.write(self.buffer, -2):
                raise EOFError("while writing")
        self.buffer.clear()
        
class BufferedStream(object):
    def __init__(self, stream, buffer_size = 1024 * 8, read_buffer_size = 0, write_buffer_size = 0):        
        self.stream = stream
        self.reader = BufferedReader(stream, Buffer(read_buffer_size or buffer_size))
        self.writer = BufferedWriter(stream, Buffer(write_buffer_size or buffer_size))

    def set_stream(self, stream):
        self.stream = stream
        self.reader.stream = stream
        self.writer.stream = stream

    def file(self):
        return CompatibleFile(self.reader, self.writer)

    def close(self):
        self.stream.close()
        del self.stream
        del self.reader
        del self.writer
        

class CompatibleFile(object):
    """A wrapper that implements python's file like object semantics on top
    of concurrence BufferedReader and or BufferedWriter. Don't create
    this object directly, but use the file() method on BufferedReader or BufferedWriter"""
    def __init__(self, reader = None, writer = None):
        self._reader = reader
        self._writer = writer

    def readlines(self):
        reader = self._reader
        buffer = reader.buffer
        while True:
            try:
                yield buffer.read_line(True)
            except BufferUnderflowError:
                try:
                    reader._read_more()
                except EOFError:
                    buffer.flip()
                    yield buffer.read_bytes(-1)
            
    def readline(self):
        return self.readlines().next()

    def read(self, n = -1):
        reader = self._reader
        buffer = reader.buffer
        s = []
        if n == -1: #read all available bytes until EOF
            while True:
                s.append(buffer.read_bytes(-1))
                try:
                    reader._read_more()
                except EOFError:
                    buffer.flip()
                    break
        else:
            while n > 0: #read uptill n avaiable bytes or EOF
                r = buffer.remaining 
                if r > 0:
                    s.append(buffer.read_bytes(min(n, r)))
                    n -= r 
                else:
                    try:
                        reader._read_more()
                    except EOFError:
                        buffer.flip()
                        break            
        return ''.join(s)

    def write(self, s):
        self._writer.write_bytes(s)

    def flush(self):
        self._writer.flush()

class BufferedStreamShared(object):
    _write_buffer_size = 1024 * 4
    _read_buffer_size = 1024 * 4

    _reader_pool = []
    _writer_pool = []

    def __init__(self, stream):
        self._stream = stream
        self._writer = None
        self._reader = None

    class _borrowed_writer(object):
        def __init__(self, stream):
            if stream._writer is None:
                if stream._writer_pool:
                    writer = stream._writer_pool.pop()
                else:
                    writer = BufferedWriter(None, Buffer(stream._write_buffer_size))
            else:
                writer = stream._writer
            writer.stream = stream._stream
            self._writer = writer
            self._stream = stream

        def __enter__(self):
            return self._writer

        def __exit__(self, type, value, traceback):
            assert self._writer.buffer.position == 0, "todo implement this case?"
            self._stream._writer_pool.append(self._writer)

    class _borrowed_reader(object):
        def __init__(self, stream):
            if stream._reader is None:
                if stream._reader_pool:
                    reader = stream._reader_pool.pop()
                else:
                    reader = BufferedReader(None, Buffer(stream._read_buffer_size))
            else:
                reader = stream._reader
            reader.stream = stream._stream
            self._reader = reader
            self._stream = stream

        def __enter__(self):
            return self._reader

        def __exit__(self, type, value, traceback):
            if self._reader.buffer.remaining:
                self._stream._reader = self._reader
            else:
                self._stream._reader_pool.append(self._reader)
                self._stream._reader = None

    def get_writer(self):
        return self._borrowed_writer(self)

    def get_reader(self):
        return self._borrowed_reader(self)

