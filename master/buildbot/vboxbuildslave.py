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
# Portions Copyright Buildbot Team Members

from __future__ import with_statement

"""A LatentSlave that uses a shell command to instantiate the slaves on demand.
"""

import os
import re
import time
import subprocess

from twisted.internet import defer, threads
from twisted.python import log

from buildbot.buildslave import AbstractLatentBuildSlave
from buildbot import interfaces

class VBoxLatentBuildSlave(AbstractLatentBuildSlave):
    def __init__(self, name, password, vm_name=None, ip=None,
                 max_builds=None, notify_on_missing=[], missing_timeout=60*20,
                 build_wait_timeout=60*10, properties={}, locks=None, keepalive_interval=3600):

        AbstractLatentBuildSlave.__init__(
            self, name, password, max_builds, notify_on_missing,
            missing_timeout, build_wait_timeout, properties, locks)

        if (vm_name is None):
            raise ValueError('You must provide a VM name')
        if (ip is None):
            raise ValueError('You must provide the IP of the VM')

        self.vm_name = vm_name
        self.ip = ip

    def buildFinished(self, *args, **kwargs):
        log.msg('%s %s build finished on VM %s' %
                (self.__class__.__name__, self.slavename, self.vm_name))
        AbstractLatentBuildSlave.buildFinished(self, *args, **kwargs)
        self.insubstantiate()

    def start_instance(self, build):
        return threads.deferToThread(self._start_instance)

    def _start_instance(self):
        log.msg('%s %s starting VM %s' %
                (self.__class__.__name__, self.slavename, self.vm_name))
        self.instance = os.system("/usr/bin/VBoxHeadless -s %s &" % self.vm_name)
        time.sleep(10)
        return subprocess.check_call("ssh %s buildslave start /var/buildslave/" % self.ip, shell=True)

    def stop_instance(self, fast=False):
        return threads.deferToThread(self._stop_instance, fast)

    def _stop_instance(self, fast=False):
        log.msg('%s %s stopping VM %s' %
                (self.__class__.__name__, self.slavename, self.vm_name))
        subprocess.check_call("ssh %s buildslave stop /var/buildslave/" % self.ip, shell=True)
        return subprocess.check_call(["/usr/bin/VBoxManage", "controlvm", self.vm_name, "savestate"])
