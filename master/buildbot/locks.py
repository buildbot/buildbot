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


from twisted.internet import defer
from twisted.python import log

from buildbot import util
from buildbot.util import service
from buildbot.util import subscription
from buildbot.util.eventual import eventually

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
        super().__init__()

        # Name of the lock
        self.lockName = name
        # Current queue, tuples (waiter, LockAccess, deferred)
        self.waiting = []
        # Current owners, tuples (owner, LockAccess)
        self.owners = []
        # maximal number of counting owners
        self.maxCount = maxCount

        # current number of claimed exclusive locks (0 or 1), must match
        # self.owners
        self._claimed_excl = 0

        # current number of claimed counting locks (0 to self.maxCount), must
        # match self.owners. Note that self.maxCount is not a strict limit, the
        # number of claimed counting locks may be higher than self.maxCount if
        # it was lowered by
        self._claimed_counting = 0

        # subscriptions to this lock being released
        self.release_subs = subscription.SubscriptionPoint(f"{repr(self)} releases")

    def __repr__(self):
        return self.description

    def setMaxCount(self, count):
        old_max_count = self.maxCount
        self.maxCount = count

        if count > old_max_count:
            self._tryWakeUp()

    def _find_waiting(self, requester):
        for idx, waiter in enumerate(self.waiting):
            if waiter[0] is requester:
                return idx
        return None

    def isAvailable(self, requester, access):
        """ Return a boolean whether the lock is available for claiming """
        debuglog(f"{self} isAvailable({requester}, {access}): self.owners={repr(self.owners)}")
        num_excl, num_counting = self._claimed_excl, self._claimed_counting

        if not access.count:
            return True

        w_index = self._find_waiting(requester)
        if w_index is None:
            w_index = len(self.waiting)

        ahead = self.waiting[:w_index]

        if access.mode == 'counting':
            # Wants counting access
            return not num_excl \
                and num_counting + len(ahead) + access.count <= self.maxCount \
                and all(w[1].mode == 'counting' for w in ahead)
        # else Wants exclusive access
        return not num_excl and not num_counting and not ahead

    def _addOwner(self, owner, access):
        self.owners.append((owner, access))
        if access.mode == 'counting':
            self._claimed_counting += access.count
        else:
            self._claimed_excl += 1

        assert (self._claimed_excl and not self._claimed_counting) \
            or (not self._claimed_excl and self._claimed_excl <= self.maxCount)

    def _removeOwner(self, owner, access):
        # returns True if owner removed, False if the lock has been already
        # released
        entry = (owner, access)
        if entry not in self.owners:
            return False

        self.owners.remove(entry)
        if access.mode == 'counting':
            self._claimed_counting -= access.count
        else:
            self._claimed_excl -= 1
        return True

    def claim(self, owner, access):
        """ Claim the lock (lock must be available) """
        debuglog(f"{self} claim({owner}, {access.mode})")
        assert owner is not None
        assert self.isAvailable(owner, access), "ask for isAvailable() first"

        assert isinstance(access, LockAccess)
        assert access.mode in ['counting', 'exclusive']
        assert isinstance(access.count, int)
        if access.mode == 'exclusive':
            assert access.count == 1
        else:
            assert access.count >= 0
        if not access.count:
            return

        self.waiting = [w for w in self.waiting if w[0] is not owner]
        self._addOwner(owner, access)

        debuglog(f" {self} is claimed '{access.mode}', {access.count} units")

    def subscribeToReleases(self, callback):
        """Schedule C{callback} to be invoked every time this lock is
        released.  Returns a L{Subscription}."""
        return self.release_subs.subscribe(callback)

    def release(self, owner, access):
        """ Release the lock """
        assert isinstance(access, LockAccess)

        if not access.count:
            return

        debuglog(f"{self} release({owner}, {access.mode}, {access.count})")
        if not self._removeOwner(owner, access):
            debuglog(f"{self} already released")
            return

        self._tryWakeUp()

        # notify any listeners
        self.release_subs.deliver()

    def _tryWakeUp(self):
        # After an exclusive access, we may need to wake up several waiting.
        # Break out of the loop when the first waiting client should not be
        # awakened.
        num_excl, num_counting = self._claimed_excl, self._claimed_counting
        for i, (w_owner, w_access, d) in enumerate(self.waiting):
            if w_access.mode == 'counting':
                if num_excl > 0 or num_counting >= self.maxCount:
                    break
                num_counting = num_counting + w_access.count
            else:
                # w_access.mode == 'exclusive'
                if num_excl > 0 or num_counting > 0:
                    break
                num_excl = num_excl + w_access.count

            # If the waiter has a deferred, wake it up and clear the deferred
            # from the wait queue entry to indicate that it has been woken.
            if d:
                self.waiting[i] = (w_owner, w_access, None)
                eventually(d.callback, self)

    def waitUntilMaybeAvailable(self, owner, access):
        """Fire when the lock *might* be available. The deferred may be fired spuriously and
        the lock is not necessarily available, thus the caller will need to check with
        isAvailable() when the deferred fires.

        A single requester must not have more than one pending waitUntilMaybeAvailable() on a
        single lock.

        The caller must guarantee, that once the returned deferred is fired, either the lock is
        checked for availability and claimed if it's available, or the it is indicated as no
        longer interesting by calling stopWaitingUntilAvailable(). The caller does not need to
        do this immediately after deferred is fired, an eventual execution is sufficient.
        """
        debuglog(f"{self} waitUntilAvailable({owner})")
        assert isinstance(access, LockAccess)
        if self.isAvailable(owner, access):
            return defer.succeed(self)
        d = defer.Deferred()

        # Are we already in the wait queue?
        w_index = self._find_waiting(owner)
        if w_index is not None:
            _, _, old_d = self.waiting[w_index]
            assert old_d is None, "waitUntilMaybeAvailable() must not be called again before the " \
                                  "previous deferred fired"
            self.waiting[w_index] = (owner, access, d)
        else:
            self.waiting.append((owner, access, d))
        return d

    def stopWaitingUntilAvailable(self, owner, access, d):
        """ Stop waiting for lock to become available. `d` must be the result of a previous call
            to `waitUntilMaybeAvailable()`. If `d` has not been woken up already by calling its
            callback, it will be done as part of this function
        """
        debuglog(f"{self} stopWaitingUntilAvailable({owner})")
        assert isinstance(access, LockAccess)

        w_index = self._find_waiting(owner)
        assert w_index is not None, "The owner was not waiting for the lock"
        _, _, old_d = self.waiting[w_index]
        if old_d is not None:
            assert d is old_d, "The supplied deferred must be a result of waitUntilMaybeAvailable()"
            del self.waiting[w_index]
            d.callback(None)
        else:
            del self.waiting[w_index]
            # if the callback has already been woken up, then it must schedule another waiter,
            # otherwise we will have an available lock with a waiter list and no-one to wake the
            # waiters up.
            self._tryWakeUp()

    def isOwner(self, owner, access):
        return (owner, access) in self.owners


class RealMasterLock(BaseLock, service.SharedService):

    def __init__(self, name):
        # the caller will want to call updateFromLockId after initialization
        super().__init__(name, 0)
        self.config_version = -1
        self._updateDescription()

    def _updateDescription(self):
        self.description = f"<MasterLock({self.lockName}, {self.maxCount})>"

    def getLockForWorker(self, workername):
        return self

    def updateFromLockId(self, lockid, config_version):
        assert self.lockName == lockid.name
        assert isinstance(config_version, int)

        self.config_version = config_version
        self.setMaxCount(lockid.maxCount)
        self._updateDescription()


class RealWorkerLock(service.SharedService):

    def __init__(self, name):
        super().__init__()

        # the caller will want to call updateFromLockId after initialization
        self.lockName = name
        self.maxCount = None
        self.maxCountForWorker = None
        self.config_version = -1
        self._updateDescription()
        self.locks = {}

    def __repr__(self):
        return self.description

    def getLockForWorker(self, workername):
        if workername not in self.locks:
            maxCount = self.maxCountForWorker.get(workername,
                                                  self.maxCount)
            lock = self.locks[workername] = BaseLock(self.lockName, maxCount)
            self._updateDescriptionForLock(lock, workername)
            self.locks[workername] = lock
        return self.locks[workername]

    def _updateDescription(self):
        self.description = \
            f"<WorkerLock({self.lockName}, {self.maxCount}, {self.maxCountForWorker})>"

    def _updateDescriptionForLock(self, lock, workername):
        lock.description = \
            f"<WorkerLock({lock.lockName}, {lock.maxCount})[{workername}] {id(lock)}>"

    def updateFromLockId(self, lockid, config_version):
        assert self.lockName == lockid.name
        assert isinstance(config_version, int)

        self.config_version = config_version

        self.maxCount = lockid.maxCount
        self.maxCountForWorker = lockid.maxCountForWorker

        self._updateDescription()

        for workername, lock in self.locks.items():
            maxCount = self.maxCountForWorker.get(workername, self.maxCount)
            lock.setMaxCount(maxCount)
            self._updateDescriptionForLock(lock, workername)


class LockAccess(util.ComparableMixin):

    """ I am an object representing a way to access a lock.

    @param lockid: LockId instance that should be accessed.
    @type  lockid: A MasterLock or WorkerLock instance.

    @param mode: Mode of accessing the lock.
    @type  mode: A string, either 'counting' or 'exclusive'.

    @param count: How many units does the access occupy
    @type  count: Integer, not negative, default is 1 for backwards
                  compatibility
    """

    compare_attrs = ('lockid', 'mode', 'count')

    def __init__(self, lockid, mode, count=1):
        self.lockid = lockid
        self.mode = mode
        self.count = count

        assert isinstance(lockid, (MasterLock, WorkerLock))
        assert mode in ['counting', 'exclusive']
        assert isinstance(count, int)
        if mode == 'exclusive':
            assert count == 1
        else:
            assert count >= 0


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

    def access(self, mode, count=1):
        """ Express how the lock should be accessed """
        assert mode in ['counting', 'exclusive']
        assert isinstance(count, int)
        assert count >= 0
        return LockAccess(self, mode, count)

    def defaultAccess(self):
        """ For buildbot 0.7.7 compatibility: When user doesn't specify an access
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


class WorkerLock(BaseLockId):

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

    def __init__(self, name, maxCount=1, maxCountForWorker=None):
        self.name = name
        self.maxCount = maxCount
        if maxCountForWorker is None:
            maxCountForWorker = {}
        self.maxCountForWorker = maxCountForWorker
        # for comparison purposes, turn this dictionary into a stably-sorted
        # list of tuples
        self._maxCountForWorkerList = tuple(
            sorted(self.maxCountForWorker.items()))
