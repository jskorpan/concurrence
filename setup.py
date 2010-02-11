
from ez_setup import use_setuptools
use_setuptools()


from setuptools import setup, find_packages
from distutils.core import Extension
from Pyrex.Distutils import build_ext
import sys

#use default libevent include and library dirs
libevent_include_dirs = []
libevent_library_dirs = []

#uncomment these if you libevent is in a differenct path (specify your specific dirs)
#libevent_include_dirs = ['/opt/libevent/include']
#libevent_library_dirs = ['/opt/libevent/lib']

VERSION = '0.3.1' #must be same as concurrence.__init__.py.__version__


if sys.platform == "win32":

    # Change these to your build of libevent
    libevent_include_dirs = ["../libevent-1.4.13-stable/", "../libevent-1.4.13-stable/WIN32-Code/"]
    libevent_library_dirs = ["../libevent-1.4.13-stable/"]
    win32_defines = [('WIN32', None), ('WIN32_LEAN_AND_MEAN', None)]
    win32_libs = ["ws2_32", "libevent"]

    setup(
      name = "concurrence",
      version=VERSION,
      author='Henk Punt',
      author_email='henkpunt@gmail.com',
      license = 'New BSD',
      url='http://opensource.hyves.org/concurrence',
      download_url='http://concurrence.googlecode.com/files/concurrence-%s.tar.gz' % VERSION,
      description='Concurrence is a framework for creating massively concurrent network applications in Python',
      package_dir = {'':'lib'},
      packages = find_packages('lib'),
      ext_modules=[
        Extension("concurrence._event", ["lib/concurrence/concurrence._event.pyx", "lib/concurrence/win32.c"], include_dirs = libevent_include_dirs, library_dirs = libevent_library_dirs, libraries = win32_libs, define_macros=win32_defines),
        Extension("concurrence.io._io", ["lib/concurrence/io/concurrence.io._io.pyx", "lib/concurrence/io/io_base.c"], include_dirs = libevent_include_dirs, library_dirs = libevent_library_dirs, libraries = win32_libs, define_macros=win32_defines),
        Extension("concurrence.database.mysql._mysql", ["lib/concurrence/database/mysql/concurrence.database.mysql._mysql.pyx"],
                  include_dirs=['lib/concurrence/io']
                  ),
        ],
      cmdclass = {'build_ext': build_ext},
        classifiers = [
                'Development Status :: 4 - Beta',
                'Environment :: Console',
                'Environment :: Web Environment',
                'Intended Audience :: Developers',
                'License :: OSI Approved :: BSD License',
                'Operating System :: OS Independent',
                'Programming Language :: Python',
                'Topic :: Software Development :: Libraries :: Python Modules'],
    )
    
else:
    setup(
      name = "concurrence",
      version=VERSION,
      author='Henk Punt',
      author_email='henkpunt@gmail.com',
      license = 'New BSD',
      url='http://opensource.hyves.org/concurrence',
      download_url='http://concurrence.googlecode.com/files/concurrence-%s.tar.gz' % VERSION,
      description='Concurrence is a framework for creating massively concurrent network applications in Python',
      package_dir = {'':'lib'},
      packages = find_packages('lib'),
      ext_modules=[
        Extension("concurrence._event", ["lib/concurrence/concurrence._event.pyx"], include_dirs = libevent_include_dirs, library_dirs = libevent_library_dirs, libraries = ["event"]),
        Extension("concurrence.io._io", ["lib/concurrence/io/concurrence.io._io.pyx", "lib/concurrence/io/io_base.c"]),
        Extension("concurrence.database.mysql._mysql", ["lib/concurrence/database/mysql/concurrence.database.mysql._mysql.pyx"],
                  include_dirs=['lib/concurrence/io']
                  ),
        ],
      cmdclass = {'build_ext': build_ext},
        classifiers = [
                'Development Status :: 4 - Beta',
                'Environment :: Console',
                'Environment :: Web Environment',
                'Intended Audience :: Developers',
                'License :: OSI Approved :: BSD License',
                'Operating System :: OS Independent',
                'Programming Language :: Python',
                'Topic :: Software Development :: Libraries :: Python Modules'],
    )

