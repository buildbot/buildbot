.. _Collapse-Request-Functions:

Collapse Request Functions
--------------------------

.. index:: Builds; collapsing


The logic Buildbot uses to decide which build request can be merged can be customized by providing
a Python function (a callable) instead of ``True`` or ``False`` described in
:ref:`Collapsing-Build-Requests`.

Arguments for the callable are:

    ``master``
        pointer to the master object, which can be used to make additional data api calls via `master.data.get`

    ``builder``
        dictionary of type :bb:rtype:`builder`

    ``req1``
        dictionary of type :bb:rtype:`buildrequest`

    ``req2``
        dictionary of type :bb:rtype:`buildrequest`

.. warning::

    The number of invocations of the callable is proportional to the square of the request queue
    length, so a long-running callable may cause undesirable delays when the queue length grows.

It should return true if the requests can be merged, and False otherwise.
For example:

.. code-block:: python

    @defer.inlineCallbacks
    def collapseRequests(master, builder, req1, req2):
        "any requests with the same branch can be merged"

        # get the buildsets for each buildrequest
        selfBuildset , otherBuildset = yield defer.gatherResults([
            master.data.get(('buildsets', req1['buildsetid'])),
            master.data.get(('buildsets', req2['buildsetid']))
            ])
        selfSourcestamps = selfBuildset['sourcestamps']
        otherSourcestamps = otherBuildset['sourcestamps']

        if len(selfSourcestamps) != len(otherSourcestamps):
            return False

        for selfSourcestamp, otherSourcestamp in zip(selfSourcestamps, otherSourcestamps):
            if selfSourcestamp['branch'] != otherSourcestamp['branch']:
                return False

        return True

    c['collapseRequests'] = collapseRequests

In many cases, the details of the :bb:rtype:`sourcestamp` and :bb:rtype:`buildrequest` are important.

In the following example, only :bb:rtype:`buildrequest` with the same "reason" are merged; thus
developers forcing builds for different reasons will see distinct builds.

Note the use of the :py:meth:`buildrequest.BuildRequest.canBeCollapsed` method to access the source
stamp compatibility algorithm:

.. code-block:: python

    @defer.inlineCallbacks
    def collapseRequests(master, builder, req1, req2):
        canBeCollapsed = yield buildrequest.BuildRequest.canBeCollapsed(master, req1, req2)
        if canBeCollapsed and req1.reason == req2.reason:
           return True
        else:
           return False
    c['collapseRequests'] = collapseRequests

Another common example is to prevent collapsing of requests coming from a :bb:step:`Trigger` step.
:bb:step:`Trigger` step can indeed be used in order to implement parallel testing of the same source.

Buildrequests will all have the same sourcestamp, but probably different properties, and shall not be collapsed.

.. note::

    In most cases, just setting ``collapseRequests=False`` for triggered builders will do the trick.

In other cases, ``parent_buildid`` from buildset can be used:

.. code-block:: python

    @defer.inlineCallbacks
    def collapseRequests(master, builder, req1, req2):
        canBeCollapsed = yield buildrequest.BuildRequest.canBeCollapsed(master, req1, req2)
        selfBuildset , otherBuildset = yield defer.gatherResults([
            master.data.get(('buildsets', req1['buildsetid'])),
            master.data.get(('buildsets', req2['buildsetid']))
        ])
        if canBeCollapsed and selfBuildset['parent_buildid'] != None and \
                otherBuildset['parent_buildid'] != None:
            return True
        else:
            return False
    c['collapseRequests'] = collapseRequests


If it's necessary to perform some extended operation to determine whether two requests can be
merged, then the ``collapseRequests`` callable may return its result via Deferred.

.. warning::

    Again, the number of invocations of the callable is proportional to the square of the request
    queue length, so a long-running callable may cause undesirable delays when the queue length
    grows.

For example:

.. code-block:: python

    @defer.inlineCallbacks
    def collapseRequests(master, builder, req1, req2):
        info1, info2 = yield defer.gatherResults([
            getMergeInfo(req1),
            getMergeInfo(req2),
        ])
        return info1 == info2

    c['collapseRequests'] = collapseRequests
