# This file is part of Buildbot.  Buildbot is free software: you can
# redistribute it and/or modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation, version 2.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51
# Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Copyright Buildbot Team Members


import os, sys
from buildbot.scripts import base
from twisted.internet import defer, reactor, protocol
from buildbot.scripts.logwatcher import LogWatcher
from buildbot.scripts.logwatcher import BuildmasterTimeoutError
from buildbot.scripts.logwatcher import ReconfigError
from buildbot.util import in_reactor

class Follower:
    def __init__(self):
        self.lw = LogWatcher()

    def follow(self):
        print "Following twistd.log until startup finished.."
        d = self.lw.start()
        d.addCallbacks(self._success, self._failure)
        return d

    def _success(self, _):
        print "The buildmaster appears to have (re)started correctly."
        return 0

    def _failure(self, why):
        if why.check(BuildmasterTimeoutError):
            print """
The buildmaster took more than 10 seconds to start, so we were unable to
confirm that it started correctly. Please 'tail twistd.log' and look for a
line that says 'configuration update complete' to verify correct startup.
"""
        elif why.check(ReconfigError):
            print """
The buildmaster appears to have encountered an error in the master.cfg config
file during startup. Please inspect and fix master.cfg, then restart the
buildmaster.
"""
        else:
            print """
Unable to confirm that the buildmaster started correctly. You may need to
stop it, fix the config file, and restart.
"""
            print why
        return 1

def launchNoDaemon(config):
    os.chdir(config['basedir'])
    sys.path.insert(0, os.path.abspath(config['basedir']))

    argv = ["twistd",
            "--no_save",
            '--nodaemon',
            "--logfile=twistd.log", # windows doesn't use the same default
            "--python=buildbot.tac"]
    sys.argv = argv

    # this is copied from bin/twistd. twisted-2.0.0 through 2.4.0 use
    # _twistw.run . Twisted-2.5.0 and later use twistd.run, even for
    # windows.
    from twisted.scripts import twistd
    twistd.run()

@in_reactor
def launch(config):
    os.chdir(config['basedir'])
    sys.path.insert(0, os.path.abspath(config['basedir']))

    # this is copied from bin/twistd. twisted-2.0.0 through 2.4.0 use
    # _twistw.run . Twisted-2.5.0 and later use twistd.run, even for
    # windows.
    script = [ "from twisted.scripts import twistd", "twistd.run()"]
    if not config['quiet']:
        script = [ "from buildbot._startupLogger import installLogger",
                "installLogger()" ] + script

    # see if we can launch the application without actually having to
    # spawn twistd, since spawning processes correctly is a real hassle
    # on windows.
    argv = [sys.executable,
            "-c",
            " ; ".join(script),
            "--no_save",
            "--logfile=twistd.log", # windows doesn't use the same default
            "--python=buildbot.tac"]

    if config['quiet']:
        # ProcessProtocol just ignores all output
        pp = protocol.ProcessProtocol()
        d = defer.succeed(0)
    else:
        follower = Follower()
        d = follower.follow()
        pp = follower.lw.pp

    reactor.spawnProcess(pp, sys.executable, argv, env=os.environ)

    return d

def start(config):
    if not base.isBuildmasterDir(config['basedir']):
        print "not a buildmaster directory"
        return 1

    if config['nodaemon']:
        launchNoDaemon(config)
        return 0

    rc = launch(config)
    return rc
