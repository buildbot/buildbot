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
RemoteStartCommand, RemoteAcceptLog, RemoteAuth, RemoteInterrupt, RemoteSlaveShutdown,\
ShellBbCommand, RemoteUpdateSendRC


class SlaveBuilder(service.Service):

    stopCommandOnShutdown = True
    remote = None
    command = None
    remoteStep = None

    def __init__(self, name):
        self.setName(name)

    def __repr__(self):
        return "<SlaveBuilder '%s' at %d>" % (self.name, id(self))

    def setServiceParent(self, parent):
        service.Service.setServiceParent(self, parent)
        self.bot = self.parent

    def setBuilddir(self, builddir):
        assert self.parent
        self.builddir = builddir
        self.basedir = os.path.join(self.bot.basedir, self.builddir)
        if not os.path.isdir(self.basedir):
            os.makedirs(self.basedir)
        data = {
            "stream": "header", 
            "data": "Creating buildir '%s' done!" % builddir,
            "logName": "stdio"
        }
        self.sendUpdate(data)

    def stopService(self):
        service.Service.stopService(self)
        if self.stopCommandOnShutdown:
            self.stopCommand()

    def activity(self):
        pass

    def remote_setMaster(self, remote):
        pass

    def remote_print(self, message):
        log.msg("SlaveBuilder.remote_print(%s): message from master: %s" %
                (self.name, message))

    def lostRemote(self, remote):
        pass

    def lostRemoteStep(self, remotestep):
        pass

    def remote_startBuild(self):
        pass

    def startCommand(self, command, args):
        log.msg("Builder %s executing command %s with args %s" % (self.name, command, args))
        if self.command:
            log.msg("leftover command, dropping it")
            self.stopCommand()
        try:
            factory = registry.getFactory(command)
        except KeyError:
            raise UnknownCommand, "unrecognized SlaveCommand '%s'" % command
        stepId = 0
        self.command = factory(self, stepId, args)

        log.msg(" startCommand:%s [id %s]" % (command,stepId))
        #self.remoteStep = stepref
        #self.remoteStep.notifyOnDisconnect(self.lostRemoteStep)
        d = self.command.doStart()
        d.addCallback(lambda res: None)
        #d.addBoth(self.commandComplete)
        return None


    def remote_interruptCommand(self, stepId, why):
        pass

    def stopCommand(self):
        pass

    @defer.inlineCallbacks
    def sendUpdate(self, data):
        assert isinstance(data, dict)
        if 'stream' in data:
            yield self.parent.callRemote(
                RemoteAcceptLog, builder=self.name, stream=data["stream"],
                logName=data["logName"], data=data["data"]
            )
        elif 'rc' in data:
            yield self.parent.callRemote(
                RemoteUpdateSendRC, builder=self.name, rc=data["rc"]
            )
        else:
            log.msg("MESSAGE TYPE UNKNOWN %s" % data) # for debug
        log.msg("sendUpdate data: %s" % pprint.pformat(data))

    def ackUpdate(self, acknum):
        pass

    def ackComplete(self, dummy):
        pass

    def _ackFailed(self, why, where):
        pass

    def commandComplete(self, failure):
        pass

    def remote_shutdown(self):
        log.msg("slave shutting down on command from master")
        log.msg("NOTE: master is using deprecated slavebuilder.shutdown method")
        reactor.stop()


class Bot(amp.AMP, service.MultiService):

    def __init__(self, basedir, usePTY, unicode_encoding=None):
        service.MultiService.__init__(self)
        self.basedir = basedir
        self.usePTY = usePTY
        self.unicode_encoding = unicode_encoding or sys.getfilesystemencoding() or 'ascii'
        self.builders = {}

    def ampList2dict(self, ampList):
        return dict([(elem['key'], elem['value']) for elem in ampList])

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
        abs_builddir = os.path.join(self.basedir, self.builddir)
        if not os.path.isdir(abs_builddir):
            os.makedirs(abs_builddir)

    @SetBuilderList.responder
    def setBuilderList(self, builders):
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

    @ShellBbCommand.responder
    def executeShell(self, **kwargs):
        builder_name = kwargs["builder"]
        builder = self.builders.get(builder_name, None)
        if "env" in kwargs:
            kwargs["env"] = self.ampList2dict(kwargs["env"])
        if "logfiles" in kwargs:
            kwargs["logfiles"] = self.ampList2dict(kwargs["logfiles"])
        if builder is None:
            return {'error': 'No such builder'}
        builder.startCommand("shell", kwargs)
        return {'error': ''}

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
