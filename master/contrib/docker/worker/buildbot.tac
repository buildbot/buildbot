import os
import sys
import warnings

from twisted.application import service
from buildslave.bot import BuildSlave


# setup worker
basedir = os.path.abspath(os.path.dirname(__file__))
application = service.Application('buildslave')

from twisted.python.log import ILogObserver, FileLogObserver

application.setComponent(ILogObserver, FileLogObserver(sys.stdout).emit)
# and worker on the same process!
buildmaster_host = os.environ.get("BUILDMASTER", 'localhost')
port = int(os.environ.get("BUILDMASTER_PORT", 19989))
workername = os.environ.get("WORKERNAME", 'docker')
passwd = os.environ.get("WORKERPASS")
if "WORKERPASS" in os.environ:
    # delete the password from the environ so that it is not leaked in the log
    del os.environ['WORKERPASS']
keepalive = 600
usepty = 0
umask = None
maxdelay = 300
allow_shutdown = None

s = BuildSlave(buildmaster_host, port, workername, passwd, basedir,
               keepalive, usepty, umask=umask, maxdelay=maxdelay,
               allow_shutdown=allow_shutdown)
s.setServiceParent(application)
