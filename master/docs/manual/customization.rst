.. _Customization:

Customization
=============

For advanced users, Buildbot acts as a framework supporting a customized build
framework.  For the most part, such configurations consist of subclasses set up
for use in a regular Buildbot configuration file.

This chapter describes some of the more common customizations made to Buildbot.
Future versions of Buildbot will ensure compatibility with the customizations
described here, and where that is not possible the changes will be announced in
the ``NEWS`` file.

.. _Merge-Request-Functions:

Merge Request Functions
=======================

.. index:: Builds; merging

The logic Buildbot uses to decide which build request can be merged can be
customized by providing a Python function (a callable) instead of ``True`` or
``False`` described in :ref:`Merging-Build-Requests`.

The callable will be invoked with three positional arguments: a
:class:`Builder` object and two :class:`BuildRequest` objects. It should return
true if the requests can be merged, and False otherwise. For example::

    def mergeRequests(builder, req1, req2):
        "any requests with the same branch can be merged"
        return req1.branch == req2.branch
    c['mergeRequests'] = mergeRequests

In many cases, the details of the :class:`SourceStamp`\s and :class:`BuildRequest`\s are important.
In this example, only :class:`BuildRequest`\s with the same "reason" are merged; thus
developers forcing builds for different reasons will see distinct builds.  Note
the use of the :func:`canBeMergedWith` method to access the source stamp
compatibility algorithm. ::

    def mergeRequests(builder, req1, req2):
        if req1.source.canBeMergedWith(req2.source) and  req1.reason == req2.reason:
           return True
        return False
    c['mergeRequests'] = mergeRequests

If it's necessary to perform some extended operation to determine whether two
requests can be merged, then the ``mergeRequests`` callable may return its
result via Deferred.  Note, however, that the number of invocations of the
callable is proportional to the square of the request queue length, so a
long-running callable may cause undesirable delays when the queue length
grows.  For example::

    def mergeRequests(builder, req1, req2):
        d = defer.gatherResults([
            getMergeInfo(req1.source.revision),
            getMergeInfo(req2.source.revision),
        ])
        def process(info1, info2):
            return info1 == info2
        d.addCallback(process)
        return d
    c['mergeRequests'] = mergeRequests

.. _Builder-Priority-Functions:

Builder Priority Functions
==========================

.. index:: Builders; priority

The :bb:cfg:`prioritizeBuilders` configuration key specifies a function which
is called with two arguments: a :class:`BuildMaster` and a list of
:class:`Builder` objects.  It should return a list of the same :class:`Builder`
objects, in the desired order.  It may also remove items from the list if
builds should not be started on those builders. If necessary, this function can
return its results via a Deferred (it is called with ``maybeDeferred``).

A simple ``prioritizeBuilders`` implementation might look like this::

    def prioritizeBuilders(buildmaster, builders):
        """Prioritize builders.  'finalRelease' builds have the highest
        priority, so they should be built before running tests, or
        creating builds."""
        builderPriorities = {
            "finalRelease": 0,
            "test": 1,
            "build": 2,
        }
        builders.sort(key=lambda b: builderPriorities.get(b.name, 0))
        return builders

    c['prioritizeBuilders'] = prioritizeBuilders

.. _Writing-Change-Sources:

Writing Change Sources
----------------------

For some version-control systems, making Bulidbot aware of new changes can be a
challenge.  If the pre-supplied classes in :ref:`Change-Sources` are not
sufficient, then you will need to write your own.

There are three approaches, one of which is not even a change source.
The first option is to write a change source that exposes some service to
which the version control system can "push" changes.  This can be more
complicated, since it requires implementing a new service, but delivers changes
to Buildbot immediately on commit.

The second option is often preferable to the first: implement a notification
service in an external process (perhaps one that is started directly by the
version control system, or by an email server) and delivers changes to Buildbot
via :ref:`PBChangeSource`.  This section does not describe this particular
approach, since it requires no customization within the buildmaster process.

The third option is to write a change source which polls for changes -
repeatedly connecting to an external service to check for new changes.  This
works well in many cases, but can produce a high load on the version control
system if polling is too frequent, and can take too long to notice changes if
the polling is not frequent enough.

.. _Writing-a-Change-Source:

Writing a Change Source
~~~~~~~~~~~~~~~~~~~~~~~

.. py:class:: buildbot.changes.base.ChangeSource

A custom change source must implement :class:`buildbot.interfaces.IChangeSource`.

The easiest way to do this is to subclass
:class:`buildbot.changes.base.ChangeSource`, implementing the :meth:`describe`
method to describe the instance. :class:`ChangeSource` is a Twisted service, so
you will need to implement the :meth:`startService` and :meth:`stopService`
methods to control the means by which your change source receives
notifications.

When the class does receive a change, it should call
``self.master.addChange(..)`` to submit it to the buildmaster.  This method
shares the same parameters as ``master.db.changes.addChange``, so consult
the API documentation for that function for details on the available arguments.

You will probably also want to set ``compare_attrs`` to the list of object
attributes which Buildbot will use to compare one change source to another when
reconfiguring.  During reconfiguration, if the new change source is different
from the old, then the old will be stopped and the new started.

.. _Writing-a-Change-Poller:

Writing a Change Poller
~~~~~~~~~~~~~~~~~~~~~~~

.. py:class:: buildbot.changes.base.PollingChangeSource

Polling is a very common means of seeking changes, so Buildbot supplies a
utility parent class to make it easier.  A poller should subclass
:class:`buildbot.changes.base.PollingChangeSource`, which is a subclass of
:class:`ChangeSource`.  This subclass implements the :meth:`Service` methods, and
causes the :meth:`poll` method to be called every ``self.pollInterval``
seconds.  This method should return a Deferred to signal its completion.

Aside from the service methods, the other concerns in the previous section
apply here, too.
