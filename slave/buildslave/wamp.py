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

from autobahn.twisted.wamp import ApplicationSession
from autobahn.twisted.wamp import Service
from buildslave import base
from twisted.application import service
from twisted.application.internet import TimerService

from twisted.internet import defer


class SlaveBuilderWamp(base.SlaveBuilderBase):
    pass


# RemoteCommand base implementation and base proxy
class ProxyBase(object):
    name = "remotecommand"

    def __init__(self, session, slavename, commandId):
        self.session = session
        self.slavename = slavename
        self.commandId = commandId

    def callRemote(self, command, *args, **kw):
        meth = getattr(self, command, None)
        if meth is None:
            return self.session.call("org.buildbot." + self.slavename + "." + self.name + "." + command,
                                     self.commandId,
                                     *args, **kw)
        else:
            return meth(command, *args, **kw)

    # Publications are for calls that dont need a response
    # Publication avoids a return message
    # This works as pub sub in wamp is ordered
    # https://github.com/tavendo/WAMP/blob/master/spec/basic.md#publish--subscribe-ordering
    def publishRemote(self, command, *args, **kw):
        return self.session.publish("org.buildslave.%s.%s.%s" % (self.slavename, self.commandId, self.name),
                                    *args, **kw)

    def notifyOnDisconnect(self, cb):
        pass

    def dontNotifyOnDisconnect(self, cb):
        pass

    def notifyDisconnected(self):
        pass


class RemoteCommandProxy(ProxyBase):
    name = "remotecommand"
    # RemoteCommand update semantics is actually pub/sub, and not RPC
    # unfortunately, crossbar does not implement pattern subscribe yet, so that is not useful
    # update = ProxyBase.publishRemote
    # close = ProxyBase.publishRemote


class FileWriterProxy(ProxyBase):
    name = "filewriter"


class FileReaderProxy(ProxyBase):
    name = "filereader"


class BotWamp(base.BotBase):
    SlaveBuilder = SlaveBuilderWamp

    @defer.inlineCallbacks
    def remote_setBuilderList(self, builders):
        builders = yield base.BotBase.remote_setBuilderList(self, builders)
        self.builders = builders
        defer.returnValue(None)

    def remote_startCommand(self, builderName, commandId, commandName, args):
        session = self.parent.session
        slavename = self.parent.name
        rc = RemoteCommandProxy(session, slavename, commandId)
        if args.get('reader') is not None:
            args['reader'] = FileReaderProxy(session, slavename, commandId)
        if args.get('writer') is not None:
            args['writer'] = FileWriterProxy(session, slavename, commandId)

        self.builders[builderName].remote_startCommand(rc, commandId, commandName, args)


class BotApplicationSession(ApplicationSession, service.MultiService):

    def __init__(self, config):
        ApplicationSession.__init__(self)
        service.MultiService.__init__(self)
        self.config = config
        self.setServiceParent(config.extra['parent'])
        self.slavename = self.parent.name
        config.extra['parent'].session = self
        self.masterid = None

    def advertiseMe(self):
        return self.publish("org.buildslave.joined", self.parent.name)

    def registerGenericCommands(self):
        endpoint = "org.buildslave.%s.%s"
        dl = []
        for methodname in ('getCommands', 'setBuilderList', 'print', 'getSlaveInfo',
                           'getVersion', 'shutdown', 'startCommand'):
            method = getattr(self.parent.bot, "remote_" + methodname)
            dl.append(self.register(method, endpoint % (self.slavename, methodname)))
        return defer.gatherResults(dl)

    def connectedToMaster(self, masterid):
        self.masterid = masterid

    def maybeDisconnectedFromMaster(self, masterid):
        # in order to avoid race condition, we listen to all master disconnection events
        if self.masterid == masterid:
            self.masterid = None
            # maybe another master wants me...
            self.advertiseMe()

    def masterConnected(self, masterid):
        self.advertiseMe()

    def onLeave(self, details):
        self.masterid = None

    @defer.inlineCallbacks
    def onJoin(self, details):
        yield self.registerGenericCommands()
        dl = []
        dl.append(self.subscribe(self.connectedToMaster,
                                 "org.buildbot.<masterid>.%s.attached" % (self.slavename)))
        dl.append(self.subscribe(self.maybeDisconnectedFromMaster,
                                 "org.buildbot.<masterid>.disconnected"))
        dl.append(self.subscribe(self.masterConnected,
                                 "org.buildbot.<masterid>.connected"))
        yield defer.gatherResults(dl)

        # if we missed a disconnected message, we still advertise ourselve every 10min
        TimerService(10 * 60, self.advertiseMe).setServiceParent(self)


def make(config):

    if config:
        return BotApplicationSession(config)
    else:
        # if no config given, return a description of this WAMPlet ..
        return {'label': 'Buildbot slave wamplet',
                'description': 'This contains all the wamp methods provided by a buildbot slave'}


class WampBuildSlave(base.BuildSlaveBase):
    Bot = BotWamp

    def __init__(self, router_url, realm, name, passwd, basedir,
                 usePTY, umask=None,
                 unicode_encoding=None, **kw):

        base.BuildSlaveBase.__init__(self, name, basedir, usePTY, umask=umask,
                                     unicode_encoding=unicode_encoding)
        self.passwd = passwd
        self.app = Service(
            url=router_url,
            realm=realm,
            make=make,
            extra=dict(parent=self),
            debug=kw.get('debug_websockets', False),
            debug_wamp=kw.get('debug_lowlevel', False),
            debug_app=kw.get('debug', False)
        )
        self.app.setServiceParent(self)
