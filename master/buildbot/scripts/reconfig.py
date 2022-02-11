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


import os
import platform
import signal

from twisted.internet import defer
from twisted.internet import reactor

from buildbot.scripts.logwatcher import BuildmasterTimeoutError
from buildbot.scripts.logwatcher import LogWatcher
from buildbot.scripts.logwatcher import ReconfigError
from buildbot.util import in_reactor
from buildbot.util import rewrap


class Reconfigurator:

    @defer.inlineCallbacks
    def run(self, basedir, quiet, timeout=None):
        # Returns "Microsoft" for Vista and "Windows" for other versions
        if platform.system() in ("Windows", "Microsoft"):
            print("Reconfig (through SIGHUP) is not supported on Windows.")
            return None

        with open(os.path.join(basedir, "twistd.pid"), "rt", encoding='utf-8') as f:
            self.pid = int(f.read().strip())
        if quiet:
            os.kill(self.pid, signal.SIGHUP)
            return None

        # keep reading twistd.log. Display all messages between "loading
        # configuration from ..." and "configuration update complete" or
        # "I will keep using the previous config file instead.", or until
        # `timeout` seconds have elapsed.

        self.sent_signal = False
        reactor.callLater(0.2, self.sighup)

        lw = LogWatcher(os.path.join(basedir, "twistd.log"), timeout=timeout)

        try:
            yield lw.start()
            print("Reconfiguration appears to have completed successfully")
            return 0
        except BuildmasterTimeoutError:
            print("Never saw reconfiguration finish.")
        except ReconfigError:
            print(rewrap("""\
                Reconfiguration failed. Please inspect the master.cfg file for
                errors, correct them, then try 'buildbot reconfig' again.
                """))
        except IOError:
            # we were probably unable to open the file in the first place
            self.sighup()
        except Exception as e:
            print(f"Error while following twistd.log: {e}")

        return 1

    def sighup(self):
        if self.sent_signal:
            return
        print(f"sending SIGHUP to process {self.pid}")
        self.sent_signal = True
        os.kill(self.pid, signal.SIGHUP)


@in_reactor
def reconfig(config):
    basedir = config['basedir']
    quiet = config['quiet']

    timeout = config.get('progress_timeout', None)
    if timeout is not None:
        try:
            timeout = float(timeout)
        except ValueError:
            print('Progress timeout must be a number')
            return 1

    r = Reconfigurator()
    return r.run(basedir, quiet, timeout=timeout)
