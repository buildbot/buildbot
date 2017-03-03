import sys

from twisted.application import service
from twisted.python.log import FileLogObserver
from twisted.python.log import ILogObserver

from buildbot.master import BuildMaster

basedir = '/var/lib/buildbot'
configfile = 'master.cfg'

# note: this line is matched against to check that this is a buildmaster
# directory; do not edit it.
application = service.Application('buildmaster')
application.setComponent(ILogObserver, FileLogObserver(sys.stdout).emit)

m = BuildMaster(basedir, configfile, umask=None)
m.setServiceParent(application)
