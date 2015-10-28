import os
import sys

from twisted.application import service
from buildslave.bot import BuildSlave


# setup slave
basedir = os.path.abspath(os.path.dirname(__file__))
application = service.Application('buildslave')

from twisted.python.log import ILogObserver, FileLogObserver

application.setComponent(ILogObserver, FileLogObserver(sys.stdout).emit)
# and slave on the same process!
buildmaster_host = os.environ.get("BUILDMASTER", 'localhost')
port = int(os.environ.get("BUILDMASTER_PORT", 19989))
slavename = os.environ.get("SLAVENAME", 'docker')
passwd = os.environ.get("SLAVEPASS")
if "SLAVEPASS" in os.environ:
    # delete the password from the environ so that it is not leaked in the log
    del os.environ['SLAVEPASS']
keepalive = 600
usepty = 0
umask = None
maxdelay = 300
allow_shutdown = None

s = BuildSlave(buildmaster_host, port, slavename, passwd, basedir,
               keepalive, usepty, umask=umask, maxdelay=maxdelay,
               allow_shutdown=allow_shutdown)
s.setServiceParent(application)
