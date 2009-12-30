# -*- test-case-name: buildbot.test.test_locks -*-

from twisted.python import log
from twisted.internet import reactor, defer
from buildbot import util

if False: # for debugging
    debuglog = log.msg
else:
    debuglog = lambda m: None

class BaseLock:
    """
    Class handling claiming and releasing of L{self}, and keeping track of
    current and waiting owners.

    @note: Ideally, we'd like to maintain FIFO order. The place to do that
           would be the L{isAvailable()} function. However, this function is
           called by builds/steps both for the first time, and after waking
           them up by L{self} from the L{self.waiting} queue. There is
           currently no way of distinguishing between them.
    """
    description = "<BaseLock>"

    def __init__(self, name, maxCount=1):
        self.name = name        # Name of the lock
        self.waiting = []       # Current queue, tuples (LockAccess, deferred)
        self.owners = []        # Current owners, tuples (owner, LockAccess)
        self.maxCount=maxCount  # maximal number of counting owners

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
            else: # mode == 'counting'
                num_counting = num_counting + 1

        assert (num_excl == 1 and num_counting == 0) \
                or (num_excl == 0 and num_counting <= self.maxCount)
        return num_excl, num_counting


    def isAvailable(self, access):
        """ Return a boolean whether the lock is available for claiming """
        debuglog("%s isAvailable(%s): self.owners=%r"
                                            % (self, access, self.owners))
        num_excl, num_counting = self._getOwnersCount()
        if access.mode == 'counting':
            # Wants counting access
            return num_excl == 0 and num_counting < self.maxCount
        else:
            # Wants exclusive access
            return num_excl == 0 and num_counting == 0

    def claim(self, owner, access):
        """ Claim the lock (lock must be available) """
        debuglog("%s claim(%s, %s)" % (self, owner, access.mode))
        assert owner is not None
        assert self.isAvailable(access), "ask for isAvailable() first"

        assert isinstance(access, LockAccess)
        assert access.mode in ['counting', 'exclusive']
        self.owners.append((owner, access))
        debuglog(" %s is claimed '%s'" % (self, access.mode))

    def release(self, owner, access):
        """ Release the lock """
        assert isinstance(access, LockAccess)

        debuglog("%s release(%s, %s)" % (self, owner, access.mode))
        entry = (owner, access)
        assert entry in self.owners
        self.owners.remove(entry)
        # who can we wake up?
        # After an exclusive access, we may need to wake up several waiting.
        # Break out of the loop when the first waiting client should not be awakened.
        num_excl, num_counting = self._getOwnersCount()
        while len(self.waiting) > 0:
            access, d = self.waiting[0]
            if access.mode == 'counting':
                if num_excl > 0 or num_counting == self.maxCount:
                    break
                else:
                    num_counting = num_counting + 1
            else:
                # access.mode == 'exclusive'
                if num_excl > 0 or num_counting > 0:
                    break
                else:
                    num_excl = num_excl + 1

            del self.waiting[0]
            reactor.callLater(0, d.callback, self)

    def waitUntilMaybeAvailable(self, owner, access):
        """Fire when the lock *might* be available. The caller will need to
        check with isAvailable() when the deferred fires. This loose form is
        used to avoid deadlocks. If we were interested in a stronger form,
        this would be named 'waitUntilAvailable', and the deferred would fire
        after the lock had been claimed.
        """
        debuglog("%s waitUntilAvailable(%s)" % (self, owner))
        assert isinstance(access, LockAccess)
        if self.isAvailable(access):
            return defer.succeed(self)
        d = defer.Deferred()
        self.waiting.append((access, d))
        return d


class RealMasterLock(BaseLock):
    def __init__(self, lockid):
        BaseLock.__init__(self, lockid.name, lockid.maxCount)
        self.description = "<MasterLock(%s, %s)>" % (self.name, self.maxCount)

    def getLock(self, slave):
        return self

class RealSlaveLock:
    def __init__(self, lockid):
        self.name = lockid.name
        self.maxCount = lockid.maxCount
        self.maxCountForSlave = lockid.maxCountForSlave
        self.description = "<SlaveLock(%s, %s, %s)>" % (self.name,
                                                        self.maxCount,
                                                        self.maxCountForSlave)
        self.locks = {}

    def __repr__(self):
        return self.description

    def getLock(self, slavebuilder):
        slavename = slavebuilder.slave.slavename
        if not self.locks.has_key(slavename):
            maxCount = self.maxCountForSlave.get(slavename,
                                                 self.maxCount)
            lock = self.locks[slavename] = BaseLock(self.name, maxCount)
            desc = "<SlaveLock(%s, %s)[%s] %d>" % (self.name, maxCount,
                                                   slavename, id(lock))
            lock.description = desc
            self.locks[slavename] = lock
        return self.locks[slavename]


class LockAccess(util.ComparableMixin):
    """ I am an object representing a way to access a lock.

    @param lockid: LockId instance that should be accessed.
    @type  lockid: A MasterLock or SlaveLock instance.

    @param mode: Mode of accessing the lock.
    @type  mode: A string, either 'counting' or 'exclusive'.
    """

    compare_attrs = ['lockid', 'mode']
    def __init__(self, lockid, mode):
        self.lockid = lockid
        self.mode = mode

        assert isinstance(lockid, (MasterLock, SlaveLock))
        assert mode in ['counting', 'exclusive']


class BaseLockId(util.ComparableMixin):
    """ Abstract base class for LockId classes.

    Sets up the 'access()' function for the LockId's available to the user
    (MasterLock and SlaveLock classes).
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



# master.cfg should only reference the following MasterLock and SlaveLock
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
    slaves, for example to limit the load on a common SVN repository.
    """

    compare_attrs = ['name', 'maxCount']
    lockClass = RealMasterLock
    def __init__(self, name, maxCount=1):
        self.name = name
        self.maxCount = maxCount

class SlaveLock(BaseLockId):
    """I am a semaphore that limits simultaneous actions on each buildslave.

    Builds and BuildSteps can declare that they wish to claim me as they run.
    Only a limited number of such builds or steps will be able to run
    simultaneously on any given buildslave. By default this number is one,
    but my maxCount parameter can be raised to allow two or three or more
    operations to happen on a single buildslave at the same time.

    Use this to protect a resource that is shared among all the builds taking
    place on each slave, for example to limit CPU or memory load on an
    underpowered machine.

    Each buildslave will get an independent copy of this semaphore. By
    default each copy will use the same owner count (set with maxCount), but
    you can provide maxCountForSlave with a dictionary that maps slavename to
    owner count, to allow some slaves more parallelism than others.

    """

    compare_attrs = ['name', 'maxCount', '_maxCountForSlaveList']
    lockClass = RealSlaveLock
    def __init__(self, name, maxCount=1, maxCountForSlave={}):
        self.name = name
        self.maxCount = maxCount
        self.maxCountForSlave = maxCountForSlave
        # for comparison purposes, turn this dictionary into a stably-sorted
        # list of tuples
        self._maxCountForSlaveList = self.maxCountForSlave.items()
        self._maxCountForSlaveList.sort()
        self._maxCountForSlaveList = tuple(self._maxCountForSlaveList)
