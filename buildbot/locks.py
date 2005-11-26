# -*- test-case-name: buildbot.test.test_locks -*-

from twisted.python import log
from twisted.internet import reactor, defer
from buildbot import util

class BaseLock:
    owner = None
    description = "<BaseLock>"

    def __init__(self, name):
        self.name = name
        self.waiting = []

    def __repr__(self):
        return self.description

    def isAvailable(self):
        log.msg("%s isAvailable: self.owner=%s" % (self, self.owner))
        return not self.owner

    def claim(self, owner):
        log.msg("%s claim(%s)" % (self, owner))
        assert owner is not None
        self.owner = owner
        log.msg(" %s is claimed" % (self,))

    def release(self, owner):
        log.msg("%s release(%s)" % (self, owner))
        assert owner is self.owner
        self.owner = None
        reactor.callLater(0, self.nowAvailable)

    def waitUntilAvailable(self, owner):
        log.msg("%s waitUntilAvailable(%s)" % (self, owner))
        assert self.owner, "You aren't supposed to call this on a free Lock"
        d = defer.Deferred()
        self.waiting.append((d, owner))
        return d

    def nowAvailable(self):
        log.msg("%s nowAvailable" % self)
        assert not self.owner
        if not self.waiting:
            return
        d,owner = self.waiting.pop(0)
        d.callback(self)


class MasterLock(BaseLock, util.ComparableMixin):
    compare_attrs = ['name']
    def __init__(self, name):
        BaseLock.__init__(self, name)
        self.description = "<MasterLock(%s) %d>" % (name, id(self))

    def getLock(self, slave):
        return self

class SlaveLock(util.ComparableMixin):
    compare_attrs = ['name']
    def __init__(self, name):
        self.name = name
        self.locks = {}

    def getLock(self, slavebuilder):
        slavename = slavebuilder.slave.slavename
        if not self.locks.has_key(slavename):
            lock = self.locks[slavename] = BaseLock(self.name)
            lock.description = "<SlaveLock(%s)[%s] %d>" % (self.name,
                                                            slavename,
                                                            id(lock))
            self.locks[slavename] = lock
        return self.locks[slavename]

