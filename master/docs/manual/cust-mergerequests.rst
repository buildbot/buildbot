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
