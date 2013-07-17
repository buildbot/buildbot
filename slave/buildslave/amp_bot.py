# -*- coding: utf-8 -*-

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


import socket
import os
import sys
import pprint

from twisted.internet import reactor, defer
from twisted.internet.protocol import Factory
from twisted.protocols import amp
from twisted.python import log
from twisted.internet.endpoints import TCP4ClientEndpoint
from twisted.application import service

import buildslave
from buildslave import monkeypatches
from buildslave.commands import registry, base
from buildslave.protocols import DebugAMP, GetInfo, SetBuilderList, RemotePrint,\
RemoteStartCommand, RemoteAcceptLog, RemoteAuth, RemoteInterrupt, RemoteSlaveShutdown


class SlaveBuilder(service.Service):

    """This is the local representation of a single Builder: it handles a
    single kind of build (like an all-warnings build). It has a name and a
    home directory. The rest of its behavior is determined by the master.
    """

    stopCommandOnShutdown = True

    # remote is a ref to the Builder object on the master side, and is set
    # when they attach. We use it to detect when the connection to the master
    # is severed.
    remote = None

    # .command points to a SlaveCommand instance, and is set while the step
    # is running. We use it to implement the stopBuild method.
    command = None

    # .remoteStep is a ref to the master-side BuildStep object, and is set
    # when the step is started
    remoteStep = None

    def __init__(self, name):
        self.setName(name)

    def __repr__(self):
        return "<SlaveBuilder '%s' at %d>" % (self.name, id(self))

    def setServiceParent(self, parent):
        pass
        # service.Service.setServiceParent(self, parent) uncommenting this line
        # will produce
        # exceptions.AttributeError: 'Bot' object has no attribute 'addService'
        self.bot = self.parent

        # note that self.parent will go away when the buildmaster's config
        # file changes and this Builder is removed (possibly because it has
        # been changed, so the Builder will be re-added again in a moment).
        # This may occur during a build, while a step is running.

    def setBuilddir(self, builddir):
        # assert self.parent
        self.builddir = builddir
        self.basedir = os.path.join(self.bot.basedir, self.builddir)
        if not os.path.isdir(self.basedir):
            os.makedirs(self.basedir)

    def stopService(self):
        service.Service.stopService(self)
        if self.stopCommandOnShutdown:
            self.stopCommand()

    def activity(self):
        # Do we need something similar?
        log.msg("activity called")

    def remote_setMaster(self, remote):
        # Do we need something similar?
        pass

    def remote_print(self, message):
        log.msg("SlaveBuilder.remote_print(%s): message from master: %s" %
                (self.name, message))

    def lostRemote(self, remote):
        # Do we need something similar?
        log.msg("lostRemote called")


    def lostRemoteStep(self, remotestep):
        # Do we need something similar?
        log.msg("lostRemoteStep called")

    # the following are Commands that can be invoked by the master-side
    # Builder
    def remote_startBuild(self):
        """This is invoked before the first step of any new build is run.  It
        doesn't do much, but masters call it so it's still here."""
        pass

    def remote_startCommand(self, environ, command, args):
        # We need to discuss how command will be executed here
        # also
        # After command started it will generate some amount of logs
        # which should be streamed to master. I think that reasonably will stream
        # log from this function, what you think?
        pass

    def remote_interruptCommand(self, stepId, why):
        # The way interrupting command will depends on how it'll started
        pass

    def stopCommand(self):
        log.msg("stopCommand called")

    # sendUpdate is invoked by the Commands we spawn
    def sendUpdate(self, data):
        pass

    def ackUpdate(self, acknum):
        pass

    def ackComplete(self, dummy):
        pass

    def _ackFailed(self, why, where):
        pass

    # this is fired by the Deferred attached to each Command
    def commandComplete(self, failure):
        pass

    def remote_shutdown(self):
        # Do we need something similar?
        pass


class Bot(amp.AMP):
    def __init__(self, basedir, usePTY, unicode_encoding=None):
        self.basedir = basedir
        self.usePTY = usePTY
        self.unicode_encoding = unicode_encoding or sys.getfilesystemencoding() or 'ascii'
        self.builders = {}

    @GetInfo.responder
    def getInfo(self):
        commands = [
            dict([('name', n), ('version', base.command_version)])
            for n in registry.getAllCommandNames()
        ]
        environ = [
            dict([('key', key), ('value', value)])
            for key, value in os.environ.copy().items()
        ]
        system = os.name
        basedir= self.basedir
        version = buildslave.version
        return {'commands': commands, 'environ': environ, 'system': system,
            'basedir': basedir, 'version': version,
        }

    @SetBuilderList.responder
    def setBuilderList(self, builders):
        retval = {}
        wanted_names = set([ builder["name"] for builder in builders ])
        wanted_dirs = set([ builder["dir"] for builder in builders ])
        wanted_dirs.add('info')
        for builder in builders:
            name = builder["name"]
            builddir = builder["dir"]
            b = self.builders.get(name, None)
            if b:
                if b.builddir != builddir:
                    log.msg("changing builddir for builder %s from %s to %s" \
                            % (name, b.builddir, builddir))
                    b.setBuilddir(builddir)
            else:
                b = SlaveBuilder(name)
                b.usePTY = self.usePTY
                b.unicode_encoding = self.unicode_encoding
                b.setServiceParent(self)
                b.setBuilddir(builddir)
                self.builders[name] = b
            retval[name] = b

        # disown any builders no longer desired
        to_remove = list(set(self.builders.keys()) - wanted_names)
        dl = defer.DeferredList([
            defer.maybeDeferred(self.builders[name].disownServiceParent)
            for name in to_remove ])
        wfd = defer.waitForDeferred(dl)
        # yield wfd ???
        wfd.getResult()

        # and *then* remove them from the builder list
        for name in to_remove:
            del self.builders[name]

        # finally warn about any leftover dirs
        for dir in os.listdir(self.basedir):
            if os.path.isdir(os.path.join(self.basedir, dir)):
                if dir not in wanted_dirs:
                    log.msg("I have a leftover directory '%s' that is not "
                            "being used by the buildmaster: you can delete "
                            "it now" % dir)

        return {'result': 0}  # return value

    @RemotePrint.responder
    def remotePrint(self, message):
        log.msg('Message from master: "%s"' % message)
        return {'result': 0}

    @RemoteStartCommand.responder
    @defer.inlineCallbacks
    def remoteStartCommand(self, environ, command, args, builder):
        log.msg('Master asks me to execute a command: "%s" "%s' % (
                command, " ".join(args)
        ))
        log.msg('For builder: "%s" with environ: %s' % (builder, pprint.pformat(environ)))
        sometext = "Just a short line"
        sometext2 = u"Привет мир! Hello world! こんにちは、世界！"
        yield self.callRemote(RemoteAcceptLog, line=sometext)
        yield self.callRemote(RemoteAcceptLog, line=sometext2)

        defer.returnValue({'result': 0, 'builder': builder})

    @RemoteInterrupt.responder
    def remoteInterrupt(self, command):
        log.msg('Interrupting command: "%s"' % command)
        return {}

    @RemoteSlaveShutdown.responder
    def remoteSlaveShutdown(self):
        log.msg('Master asks me to stop')
        reactor.stop()
        return {}


def sendAuthReq(ampProto):
    user, password = 'user', 'password'
    my_features = [{'key': 'connection_type', 'value': 'slave'}]
    return ampProto.callRemote(RemoteAuth, user=user, password=password, features=my_features)


class BuildSlave(service.MultiService):
    def __init__(self, buildmaster_host, port, name, passwd, basedir,
                 keepalive, usePTY, keepaliveTimeout=None, umask=None,
                 maxdelay=300, unicode_encoding=None, allow_shutdown=None):

        # note: keepaliveTimeout is ignored, but preserved here for
        # backward-compatibility
        service.MultiService.__init__(self)
        if keepalive == 0:
            keepalive = None
        self.umask = umask
        self.basedir = basedir
        self.shutdown_loop = None
        if allow_shutdown == 'signal':
            if not hasattr(signal, 'SIGHUP'):
                raise ValueError("Can't install signal handler")
        elif allow_shutdown == 'file':
            self.shutdown_file = os.path.join(basedir, 'shutdown.stamp')
            self.shutdown_mtime = 0
        self.allow_shutdown = allow_shutdown

        endpoint = TCP4ClientEndpoint(reactor, buildmaster_host, port)
        factory = Factory()
        factory.protocol = lambda: Bot(basedir, usePTY, unicode_encoding=unicode_encoding)
        ampProto = endpoint.connect(factory)
        ampProto.addCallback(sendAuthReq)
        ampProto.addCallback(lambda vector: log.msg("Master's features: %s" % vector))

    def startService(self):
        # first, apply all monkeypatches
        monkeypatches.patch_all()

        log.msg("Starting BuildSlave -- version: %s" % buildslave.version)

        self.recordHostname(self.basedir)
        if self.umask is not None:
            os.umask(self.umask)

        service.MultiService.startService(self)

        if self.allow_shutdown == 'signal':
            log.msg("Setting up SIGHUP handler to initiate shutdown")
            signal.signal(signal.SIGHUP, self._handleSIGHUP)
        elif self.allow_shutdown == 'file':
            log.msg("Watching %s's mtime to initiate shutdown" % self.shutdown_file)
            if os.path.exists(self.shutdown_file):
                self.shutdown_mtime = os.path.getmtime(self.shutdown_file)
            self.shutdown_loop = l = task.LoopingCall(self._checkShutdownFile)
            l.start(interval=10)

    def stopService(self):
        if self.shutdown_loop:
            self.shutdown_loop.stop()
            self.shutdown_loop = None
        return service.MultiService.stopService(self)

    def recordHostname(self, basedir):
        "Record my hostname in twistd.hostname, for user convenience"
        log.msg("recording hostname in twistd.hostname")
        filename = os.path.join(basedir, "twistd.hostname")

        try:
            hostname = os.uname()[1] # only on unix
        except AttributeError:
            # this tends to fail on non-connected hosts, e.g., laptops
            # on planes
            hostname = socket.getfqdn()

        try:
            open(filename, "w").write("%s\n" % hostname)
        except:
            log.msg("failed - ignoring")

    def _handleSIGHUP(self, *args):
        log.msg("Initiating shutdown because we got SIGHUP")
        reactor.stop()

    def _checkShutdownFile(self):
        if os.path.exists(self.shutdown_file) and \
                os.path.getmtime(self.shutdown_file) > self.shutdown_mtime:
            log.msg("Initiating shutdown because %s was touched" % self.shutdown_file)
            self.gracefulShutdown()

            # In case the shutdown fails, update our mtime so we don't keep
            # trying to shutdown over and over again.
            # We do want to be able to try again later if the master is
            # restarted, so we'll keep monitoring the mtime.
            self.shutdown_mtime = os.path.getmtime(self.shutdown_file)
