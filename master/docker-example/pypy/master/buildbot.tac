import sys

from buildbot.master import BuildMaster
from twisted.application import service
from twisted.python.log import FileLogObserver, ILogObserver

basedir = '/usr/src/app'
configfile = 'master.cfg'

# note: this line is matched against to check that this is a buildmaster
# directory; do not edit it.
application = service.Application('buildmaster')
application.setComponent(ILogObserver, FileLogObserver(sys.stdout).emit)

m = BuildMaster(basedir, configfile, umask=None)
m.setServiceParent(application)
