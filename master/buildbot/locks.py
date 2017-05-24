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

from __future__ import absolute_import
from __future__ import print_function

from twisted.internet import defer
from twisted.python import log

from buildbot import util
from buildbot.util import subscription
from buildbot.util.eventual import eventually
from buildbot.worker_transition import WorkerAPICompatMixin
from buildbot.worker_transition import deprecatedWorkerModuleAttribute
from buildbot.worker_transition import reportDeprecatedWorkerNameUsage

if False:  # for debugging  pylint: disable=using-constant-test
    debuglog = log.msg
else:
    debuglog = lambda m: None  # noqa


class BaseLock:

    """
    Class handling claiming and releasing of L{self}, and keeping track of
    current and waiting owners.

    We maintain the wait queue in FIFO order, and ensure that counting waiters
    in the queue behind exclusive waiters cannot acquire the lock. This ensures
    that exclusive waiters are not starved.
    """
    description = "<BaseLock>"

    def __init__(self, name, maxCount=1):
        # Name of the lock
        self.name = name
        # Current queue, tuples (waiter, LockAccess, deferred)
        self.waiting = []
        # Current owners, tuples (owner, LockAccess)
        self.owners = []
        # maximal number of counting owners
        self.maxCount = maxCount

        # subscriptions to this lock being released
        self.release_subs = subscription.SubscriptionPoint("%r releases"
                                                           % (self,))

    def __repr__(self):
        return self.description

    def _getOwnersCount(self):
        """ Return the number of current exclusive and counting owners.

            @return: Tuple (number exclusive owners, number counting owners)
        """
        num_excl, num_counting = 0, 0
        for owner in self.owners:
            if owner[1].mode == 'exclusive':
                num_excl = num_excl + 1
            else:  # mode == 'counting'
                num_counting = num_counting + 1

        assert (num_excl == 1 and num_counting == 0) \
            or (num_excl == 0 and num_counting <= self.maxCount)
        return num_excl, num_counting

    def isAvailable(self, requester, access):
        """ Return a boolean whether the lock is available for claiming """
        debuglog("%s isAvailable(%s, %s): self.owners=%r"
                 % (self, requester, access, self.owners))
        num_excl, num_counting = self._getOwnersCount()

        # Find all waiters ahead of the requester in the wait queue
        for idx, waiter in enumerate(self.waiting):
            if waiter[0] == requester:
                w_index = idx
                break
        else:
            w_index = len(self.waiting)
        ahead = self.waiting[:w_index]

        if access.mode == 'counting':
            # Wants counting access
            return num_excl == 0 and num_counting + len(ahead) < self.maxCount \
                and all([w[1].mode == 'counting' for w in ahead])
        # else Wants exclusive access
        return num_excl == 0 and num_counting == 0 and not ahead

    def claim(self, owner, access):
        """ Claim the lock (lock must be available) """
        debuglog("%s claim(%s, %s)" % (self, owner, access.mode))
        assert owner is not None
        assert self.isAvailable(owner, access), "ask for isAvailable() first"

        assert isinstance(access, LockAccess)
        assert access.mode in ['counting', 'exclusive']
        self.waiting = [w for w in self.waiting if w[0] != owner]
        self.owners.append((owner, access))
        debuglog(" %s is claimed '%s'" % (self, access.mode))

    def subscribeToReleases(self, callback):
        """Schedule C{callback} to be invoked every time this lock is
        released.  Returns a L{Subscription}."""
        return self.release_subs.subscribe(callback)

    def release(self, owner, access):
        """ Release the lock """
        assert isinstance(access, LockAccess)

        debuglog("%s release(%s, %s)" % (self, owner, access.mode))
        entry = (owner, access)
        if entry not in self.owners:
            debuglog("%s already released" % self)
            return
        self.owners.remove(entry)
        # who can we wake up?
        # After an exclusive access, we may need to wake up several waiting.
        # Break out of the loop when the first waiting client should not be
        # awakened.
        num_excl, num_counting = self._getOwnersCount()
        for i, (w_owner, w_access, d) in enumerate(self.waiting):
            if w_access.mode == 'counting':
                if num_excl > 0 or num_counting == self.maxCount:
                    break
                else:
                    num_counting = num_counting + 1
            else:
                # w_access.mode == 'exclusive'
                if num_excl > 0 or num_counting > 0:
                    break
                else:
                    num_excl = num_excl + 1

            # If the waiter has a deferred, wake it up and clear the deferred
            # from the wait queue entry to indicate that it has been woken.
            if d:
                self.waiting[i] = (w_owner, w_access, None)
                eventually(d.callback, self)

        # notify any listeners
        self.release_subs.deliver()

    def waitUntilMaybeAvailable(self, owner, access):
        """Fire when the lock *might* be available. The caller will need to
        check with isAvailable() when the deferred fires. This loose form is
        used to avoid deadlocks. If we were interested in a stronger form,
        this would be named 'waitUntilAvailable', and the deferred would fire
        after the lock had been claimed.
        """
        debuglog("%s waitUntilAvailable(%s)" % (self, owner))
        assert isinstance(access, LockAccess)
        if self.isAvailable(owner, access):
            return defer.succeed(self)
        d = defer.Deferred()

        # Are we already in the wait queue?
        w = [i for i, w in enumerate(self.waiting) if w[0] == owner]
        if w:
            self.waiting[w[0]] = (owner, access, d)
        else:
            self.waiting.append((owner, access, d))
        return d

    def stopWaitingUntilAvailable(self, owner, access, d):
        debuglog("%s stopWaitingUntilAvailable(%s)" % (self, owner))
        assert isinstance(access, LockAccess)
        assert (owner, access, d) in self.waiting
        self.waiting = [w for w in self.waiting if w[0] != owner]

    def isOwner(self, owner, access):
        return (owner, access) in self.owners


class RealMasterLock(BaseLock):

    def __init__(self, lockid):
        BaseLock.__init__(self, lockid.name, lockid.maxCount)
        self.description = "<MasterLock(%s, %s)>" % (self.name, self.maxCount)

    def getLock(self, worker):
        return self


class RealWorkerLock:

    def __init__(self, lockid):
        self.name = lockid.name
        self.maxCount = lockid.maxCount
        self.maxCountForWorker = lockid.maxCountForWorker
        self.description = "<WorkerLock(%s, %s, %s)>" % (self.name,
                                                         self.maxCount,
                                                         self.maxCountForWorker)
        self.locks = {}

    def __repr__(self):
        return self.description

    def getLock(self, worker):
        workername = worker.workername
        if workername not in self.locks:
            maxCount = self.maxCountForWorker.get(workername,
                                                  self.maxCount)
            lock = self.locks[workername] = BaseLock(self.name, maxCount)
            desc = "<WorkerLock(%s, %s)[%s] %d>" % (self.name, maxCount,
                                                    workername, id(lock))
            lock.description = desc
            self.locks[workername] = lock
        return self.locks[workername]


class LockAccess(util.ComparableMixin):

    """ I am an object representing a way to access a lock.

    @param lockid: LockId instance that should be accessed.
    @type  lockid: A MasterLock or WorkerLock instance.

    @param mode: Mode of accessing the lock.
    @type  mode: A string, either 'counting' or 'exclusive'.
    """

    compare_attrs = ('lockid', 'mode')

    def __init__(self, lockid, mode, _skipChecks=False):
        self.lockid = lockid
        self.mode = mode

        if not _skipChecks:
            # these checks fail with mock < 0.8.0 when lockid is a Mock
            # TODO: remove this in Buildbot-0.9.0+
            assert isinstance(lockid, (MasterLock, WorkerLock))
            assert mode in ['counting', 'exclusive']


class BaseLockId(util.ComparableMixin):

    """ Abstract base class for LockId classes.

    Sets up the 'access()' function for the LockId's available to the user
    (MasterLock and WorkerLock classes).
    Derived classes should add
    - Comparison with the L{util.ComparableMixin} via the L{compare_attrs}
      class variable.
    - Link to the actual lock class should be added with the L{lockClass}
      class variable.
    """

    def access(self, mode):
        """ Express how the lock should be accessed """
        assert mode in ['counting', 'exclusive']
        return LockAccess(self, mode)

    def defaultAccess(self):
        """ For buildbot 0.7.7 compability: When user doesn't specify an access
            mode, this one is chosen.
        """
        return self.access('counting')


# master.cfg should only reference the following MasterLock and WorkerLock
# classes. They are identifiers that will be turned into real Locks later,
# via the BotMaster.getLockByID method.
class MasterLock(BaseLockId):

    """I am a semaphore that limits the number of simultaneous actions.

    Builds and BuildSteps can declare that they wish to claim me as they run.
    Only a limited number of such builds or steps will be able to run
    simultaneously. By default this number is one, but my maxCount parameter
    can be raised to allow two or three or more operations to happen at the
    same time.

    Use this to protect a resource that is shared among all builders and all
    workers, for example to limit the load on a common SVN repository.
    """

    compare_attrs = ('name', 'maxCount')
    lockClass = RealMasterLock

    def __init__(self, name, maxCount=1):
        self.name = name
        self.maxCount = maxCount


class WorkerLock(BaseLockId, WorkerAPICompatMixin):

    """I am a semaphore that limits simultaneous actions on each worker.

    Builds and BuildSteps can declare that they wish to claim me as they run.
    Only a limited number of such builds or steps will be able to run
    simultaneously on any given worker. By default this number is one,
    but my maxCount parameter can be raised to allow two or three or more
    operations to happen on a single worker at the same time.

    Use this to protect a resource that is shared among all the builds taking
    place on each worker, for example to limit CPU or memory load on an
    underpowered machine.

    Each worker will get an independent copy of this semaphore. By
    default each copy will use the same owner count (set with maxCount), but
    you can provide maxCountForWorker with a dictionary that maps workername to
    owner count, to allow some workers more parallelism than others.

    """

    compare_attrs = ('name', 'maxCount', '_maxCountForWorkerList')
    lockClass = RealWorkerLock

    def __init__(self, name, maxCount=1, maxCountForWorker=None,
                 # deprecated, use `maxCountForWorker` instead
                 maxCountForSlave=None
                 ):
        # Deprecated API support.
        if maxCountForSlave is not None:
            reportDeprecatedWorkerNameUsage(
                "'maxCountForSlave' keyword argument is deprecated, "
                "use 'maxCountForWorker' instead")
            assert maxCountForWorker is None
            maxCountForWorker = maxCountForSlave

        self.name = name
        self.maxCount = maxCount
        if maxCountForWorker is None:
            maxCountForWorker = {}
        self.maxCountForWorker = maxCountForWorker
        self._registerOldWorkerAttr("maxCountForWorker")
        # for comparison purposes, turn this dictionary into a stably-sorted
        # list of tuples
        self._maxCountForWorkerList = tuple(
            sorted(self.maxCountForWorker.items()))


deprecatedWorkerModuleAttribute(locals(), WorkerLock)
