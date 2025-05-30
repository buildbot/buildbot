import os
import sys

from twisted.application import service
from twisted.logger import ILogObserver
from twisted.logger import textFileLogObserver
from twisted.logger import LogLevelFilterPredicate
from twisted.logger import FilteringLogObserver

from buildbot.master import BuildMaster

basedir = os.environ.get("BUILDBOT_BASEDIR",
    os.path.abspath(os.path.dirname(__file__)))
configfile = 'master.cfg'

# note: this line is matched against to check that this is a buildmaster
# directory; do not edit it.
application = service.Application('buildmaster')
application.setComponent(
    ILogObserver,
    FilteringLogObserver(
        textFileLogObserver(sys.stdout), predicates=[LogLevelFilterPredicate()]
    ),
)

m = BuildMaster(basedir, configfile, umask=None)
m.setServiceParent(application)
