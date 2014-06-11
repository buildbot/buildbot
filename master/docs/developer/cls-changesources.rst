Change Sources
==============

.. py:module:: buildbot.changes.base

ChangeSource
============

.. py:class:: ChangeSource

    This is the base class for change sources.

    Subclasses should override the inherited :py:meth:`~buildbot.util.service.ClusteredService.activate` and :py:meth:`~buildbot.util.service.ClusteredService.deactivate` methods if necessary to handle initialization and shutdown.

    Change sources which are active on every master should, instead, override ``startService`` and ``stopService``.

PollingChangeSource
===================

.. py:class:: PollingChangeSource

    This is a subclass of :py:class:`ChangeSource` which adds polling behavior.
    Its constructor accepts the ``pollInterval`` and ``pollAtLaunch`` arguments as documented for most built-in change sources.

    Subclasses should override the ``poll`` method.
    This method may return a Deferred.
    Calls to ``poll`` will not overlap.
