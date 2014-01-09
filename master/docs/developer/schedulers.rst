.. _Writing-Schedulers:

Writing Schedulers
==================

Buildbot schedulers are the process objects responsible for requesting builds.

Schedulers are free to decide when to request builds, and to define the parameters of the builds.
Many schedulers (e.g., :bb:sched:`SingleBranchScheduler`) request builds in response to changes from change sources.
Others, such as :bb:sched:`Nightly`, request builds at specific times.
Still others, like :bb:sched:`ForceScheduler`, :bb:sched:`Try_Jobdir`, or :bb:sched:`Triggerable`, respond to external inputs.

Each scheduler has a unique name, and within a Buildbot cluster, can be active on at most one master.
If a scheduler is configured on multiple masters, it will be inactive on all but one master.
This provides a form of non-revertive failover for schedulers: if an active scheduler's master fails, an inactive instance of that scheduler on another master will become active.

API Stability
-------------

Until Buildbot reaches version 1.0.0, API stability is not guaranteed.
The instructions in this document may change incompatibly until that time.

Implementing A Scheduler
------------------------

A scheduler is a subclass of :py:class:`~buildbot.schedulers.base.BaseScheduler`.

The constructor's arguments form the scheduler's configuration.
The first two arguments are ``name`` and ``builderNames``, and are positional.
The remaining arguments are keyword arguments, and the subclass's constructor should accept ``**kwargs`` to pass on to the parent class along with the positional arguments. ::

    class MyScheduler(base.BaseScheduler):
        def __init__(self, name, builderNames, arg1=None, arg2=None, **kwargs):
            base.BaseScheduler.__init__(self, name, builderNames, **kwargs)
            self.arg1 = arg1
            self.arg2 = arg2

Schedulers are Twisted services, so they can implement ``startService`` and ``stopService``.
However, it is more common for scheduler subclasses to override ``startActivity`` and ``stopActivity`` instead.
See below.

Consuming Changes
-----------------

A scheduler that needs to be notified of new changes should call :py:meth:`~buildbot.schedulers.base.BaseScheduler.startConsumingChanges` when it becomes active.
Change consumption will automatically stop when the scheduler becomes inactive.

Once consumption has started, the :py:meth:`~buildbot.schedulers.base.BaseScheduler.gotChange` method is invoked for each new change.
The scheduler is free to do whatever it likes in this method.

Adding Buildsets
----------------

To add a new buildset, subclasses should call one of the parent-class methods with the prefix ``addBuildsetFor``.
These methods call :py:meth:`~buildbot.db.buildsets.BuildsetConnector.addBuildset` after applying behaviors common to all schedulers

Any of these methods can be called at any time.

Handling Reconfiguration
------------------------

When the configuration for a scheduler changes, Buildbot deactivates, stops and removes the old scheduler, then adds, starts, and maybe activates the new scheduler.
Buildbot determines whether a scheduler has changed by subclassing :py:class:`~buildbot.util.ComparableMixin`.
See the documentation for class for an explanation of the ``compare_attrs`` attribute.

.. note::

    In a future version, schedulers will be converted to handle reconfiguration as reconfigurable services, and will no longer require ``compare_attrs`` to be set.

Becoming Active and Inactive
----------------------------

An inactive scheduler should not do anything that might interfere with an active scheduler of the same name.

Simple schedulers can consult the :py:attr:`~buildbot.schedulers.base.BaseScheduler.active` attribute to determine whether the scheduler is active.

Most schedulers, however, will implement the ``activate`` method to begin any processing expected of an active scheduler.
That may involve calling :py:meth:`~buildbot.schedulers.base.BaseScheduler.startConsumingChanges`, beginning a ``LoopingCall``, or subscribing to messages.

Any processing begun by the ``activate`` method, or by an active scheduler, should be stopped by the ``deactivate`` method.
The ``deactivate`` method's Deferred should not fire until such processing has completely stopped.
Schedulers must up-call the parent class's ``activate`` and ``deactivate`` methods!

Keeping State
-------------

The :py:class:`~buildbot.schedulers.base.BaseScheduler` class provides :py:meth:`~buildbot.schedulers.base.BaseScheduler.getState` and :py:meth:`~buildbot.schedulers.base.BaseScheduler.setState` methods to get and set state values for the scheduler.
Active scheduler instances should use these functions to store persistent scheduler state, such that if they fail or become inactive, other instances can pick up where they leave off.
A scheduler can cache its state locally, only calling ``getState`` when it first becomes active.
However, it is best to keep the state as up-to-date as possible, by calling ``setState`` any time the state changes.
This prevents loss of state from an unexpected master failure.

Note that the state-related methods do not use locks of any sort.
It is up to the caller to ensure that no race conditions exist between getting and setting state.
Generally, it is sufficient to rely on there being only one running instance of a scheduler, and cache state in memory.
