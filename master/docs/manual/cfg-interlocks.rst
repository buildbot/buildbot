.. -*- rst -*-
.. _Interlocks:

Interlocks
----------

.. contents::
   :depth: 1
   :local:

Until now, we assumed that a master can run builds at any slave whenever needed or desired.
Some times, you want to enforce additional constraints on builds.
For reasons like limited network bandwidth, old slave machines, or a self-willed data base server, you may want to limit the number of builds (or build steps) that can access a resource.

.. _Access-Modes:

Access Modes
~~~~~~~~~~~~

The mechanism used by Buildbot is known as the read/write lock [#]_.
It allows either many readers or a single writer but not a combination of readers and writers.
The general lock has been modified and extended for use in Buildbot.
Firstly, the general lock allows an infinite number of readers.
In Buildbot, we often want to put an upper limit on the number of readers, for example allowing two out of five possible builds at the same time.
To do this, the lock counts the number of active readers.
Secondly, the terms *read mode* and *write mode* are confusing in Buildbot context.
They have been replaced by *counting mode* (since the lock counts them) and *exclusive mode*.
As a result of these changes, locks in Buildbot allow a number of builds (up to some fixed number) in counting mode, or they allow one build in exclusive mode.

.. note::

   Access modes are specified when a lock is used.
   That is, it is possible to have a single lock that is used by several slaves in counting mode, and several slaves in exclusive mode.
   In fact, this is the strength of the modes: accessing a lock in exclusive mode will prevent all counting-mode accesses.

Count
~~~~~

Often, not all slaves are equal.
To allow for this situation, Buildbot allows to have a separate upper limit on the count for each slave.
In this way, you can have at most 3 concurrent builds at a fast slave, 2 at a slightly older slave, and 1 at all other slaves.

Scope
~~~~~

The final thing you can specify when you introduce a new lock is its scope.
Some constraints are global -- they must be enforced over all slaves.
Other constraints are local to each slave.
A *master lock* is used for the global constraints.
You can ensure for example that at most one build (of all builds running at all slaves) accesses the data base server.
With a *slave lock* you can add a limit local to each slave.
With such a lock, you can for example enforce an upper limit to the number of active builds at a slave, like above.

Examples
~~~~~~~~

Time for a few examples.
Below a master lock is defined to protect a data base, and a slave lock is created to limit the number of builds at each slave.

::

    from buildbot.plugins import util

    db_lock = util.MasterLock("database")
    build_lock = util.SlaveLock("slave_builds",
                                maxCount=1,
                                maxCountForSlave={'fast': 3, 'new': 2})

After importing locks from buildbot, :data:`db_lock` is defined to be a master lock.
The ``database`` string is used for uniquely identifying the lock.
At the next line, a slave lock called :data:`build_lock` is created.
It is identified by the ``slave_builds`` string.
Since the requirements of the lock are a bit more complicated, two optional arguments are also specified.
The ``maxCount`` parameter sets the default limit for builds in counting mode to ``1``.
For the slave called ``'fast'`` however, we want to have at most three builds, and for the slave called ``'new'`` the upper limit is two builds running at the same time.

The next step is accessing the locks in builds.
Buildbot allows a lock to be used during an entire build (from beginning to end), or only during a single build step.
In the latter case, the lock is claimed for use just before the step starts, and released again when the step ends.
To prevent deadlocks, [#]_ it is not possible to claim or release locks at other times.

To use locks, you add them with a ``locks`` argument to a build or a step.
Each use of a lock is either in counting mode (that is, possibly shared with other builds) or in exclusive mode, and this is indicated with the syntax ``lock.access(mode)``, where :data:`mode` is one of ``"counting"`` or ``"exclusive"``.

A build or build step proceeds only when it has acquired all locks.
If a build or step needs a lot of locks, it may be starved [#]_ by other builds that need fewer locks.

To illustrate use of locks, a few examples.

::

    from buildbot.plugins import util, steps

    db_lock = util.MasterLock("database")
    build_lock = util.SlaveLock("slave_builds",
                                maxCount=1,
                                maxCountForSlave={'fast': 3, 'new': 2})

    f = util.BuildFactory()
    f.addStep(steps.SVN(svnurl="http://example.org/svn/Trunk"))
    f.addStep(steps.ShellCommand(command="make all"))
    f.addStep(steps.ShellCommand(command="make test",
                                 locks=[db_lock.access('exclusive')]))

    b1 = {
        'name': 'full1',
        'slavename': 'fast',
        'builddir': 'f1',
        'factory': f,
        'locks': [build_lock.access('counting')]
    }
    b2 = {
        'name': 'full2',
        'slavename': 'new',
        'builddir': 'f2',
        'factory': f,
        'locks': [build_lock.access('counting')]
    }
    b3 = {
        'name': 'full3',
        'slavename': 'old',
        'builddir': 'f3',
        'factory': f,
        'locks': [build_lock.access('counting')]
    }
    b4 = {
        'name': 'full4',
        'slavename': 'other',
        'builddir': 'f4',
        'factory': f,
        'locks': [build_lock.access('counting')]
    }

    c['builders'] = [b1, b2, b3, b4]

Here we have four slaves :data:`b1`, :data:`b2`, :data:`b3`, and :data:`b4`.
Each slave performs the same checkout, make, and test build step sequence.
We want to enforce that at most one test step is executed between all slaves due to restrictions with the data base server.
This is done by adding the ``locks=`` parameter with the third step.
It takes a list of locks with their access mode.
In this case only the :data:`db_lock` is needed.
The exclusive access mode is used to ensure there is at most one slave that executes the test step.

In addition to exclusive accessing the data base, we also want slaves to stay responsive even under the load of a large number of builds being triggered.
For this purpose, the slave lock called :data:`build_lock` is defined.
Since the restraint holds for entire builds, the lock is specified in the builder with ``'locks': [build_lock.access('counting')]``.

Note that you will occasionally see ``lock.access(mode)`` written as ``LockAccess(lock, mode)``.
The two are equivalent, but the former is preferred.

.. [#] See http://en.wikipedia.org/wiki/Read/write_lock_pattern for more information.

.. [#] Deadlock is the situation where two or more slaves each hold a lock in exclusive mode, and in addition want to claim the lock held by the other slave exclusively as well.
       Since locks allow at most one exclusive user, both slaves will wait forever.

.. [#] Starving is the situation that only a few locks are available, and they are immediately grabbed by another build.
       As a result, it may take a long time before all locks needed by the starved build are free at the same time.
