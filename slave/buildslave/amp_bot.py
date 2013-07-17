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


class Bot(amp.AMP, service.MultiService):
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

    def setBuilddir(self, builddir):
        self.builddir = builddir
        self.basedir = os.path.join(self.basedir, self.builddir)
        if not os.path.isdir(self.basedir):
            os.makedirs(self.basedir)

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
                if b != builddir:
                    log.msg("changing builddir for builder %s from %s to %s" \
                            % (name, b, builddir))
                    self.setBuilddir(builddir)
            else:
                self.setBuilddir(builddir)
                self.builders[name] = builddir

        to_remove = list(set(self.builders.keys()) - wanted_names)
        # remove any builders no longer desired from the builder list
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
