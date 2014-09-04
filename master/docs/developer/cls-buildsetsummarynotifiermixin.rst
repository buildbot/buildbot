BuildSetSummaryNotifierMixin
============================

.. py:currentmodule:: buildbot.status.buildset

Some status notifiers will want to report the status of all builds all at once for a particular buildset, instead of reporting each build individually as it finishes.
In order to do this, the status notifier must wait for all builds to finish, collect their results, and then report a kind of summary on all of the collected results.
The act of waiting for and collecting the results of all of the builders is implemented via :class:`BuildSetSummaryNotifierMixin`, to be subclassed by a status notification implementation.

BuildSetSummaryNotifierMixin
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. py:class:: buildbot.status.buildset.BuildSetSummaryNotifierMixin::

    This class provides some helper methods for implementing a status notification that provides notifications for all build results for a buildset at once.

    This class provides the following methods:

    .. py:method:: summarySubscribe()

        Call this to start receiving :meth:`sendBuildSetSummary` callbacks.
        Typically this will be called from the subclass's :meth:`startService` method.

    .. py:method:: summaryUnsubscribe()

        Call this to stop receiving :meth:`sendBuildSetSummary` callbacks.
        Typically this will be called from the subclass's :meth:`stopService` method.

    The following methods are hooks to be implemented by the subclass.

    .. py:method:: sendBuildSetSummary(buildset, builds)

        :param buildset: A :class:`BuildSet` object
        :param builds: A list of :class:`Build` objects

        This method must be implemented by the subclass.
        This method is called when all of the builds for a buildset have finished, and it should initiate sending a summary status for the buildset.

    The following attributes must be provided by the subclass.

    .. py:attribute:: master

        This must point to the :py:class:`BuildMaster` object.
