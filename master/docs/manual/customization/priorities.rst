.. _Priorities:

Priorities
==========

This section describes various priority functions that can be used to control the order in which builds are processed.

.. _Builder-Priority-Functions:

Builder Priority Functions
--------------------------

.. index:: Builders; priority

The :bb:cfg:`prioritizeBuilders` configuration key specifies a function which is called with two
arguments: a :class:`BuildMaster` and a list of :class:`Builder` objects. It should return a list
of the same :class:`Builder` objects, in the desired order. It may also remove items from the list
if builds should not be started on those builders. If necessary, this function can return its
results via a Deferred (it is called with ``maybeDeferred``).

A simple ``prioritizeBuilders`` implementation might look like this:

.. code-block:: python

    def prioritizeBuilders(buildmaster, builders):
        """Prioritize builders. 'finalRelease' builds have the highest
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

If the change frequency is higher than the turn-around of the builders,
the following approach might be helpful:

.. code-block:: python

    from buildbot.util.async_sort import async_sort
    from twisted.internet import defer

    @defer.inlineCallbacks
    def prioritizeBuilders(buildmaster, builders):
        """Prioritize builders. First, prioritize inactive builders.
        Second, consider the last time a job was completed (no job is infinite past).
        Third, consider the time the oldest request has been queued.
        This provides a simple round-robin scheme that works with collapsed builds."""

        def isBuilding(b):
            return bool(b.building) or bool(b.old_building)

        @defer.inlineCallbacks
        def key(b):
            newest_complete_time = yield b.getNewestCompleteTime()
            if newest_complete_time is None:
                newest_complete_time = datetime.datetime.min

            oldest_request_time = yield b.getOldestRequestTime()
            if oldest_request_time is None:
                oldest_request_time = datetime.datetime.min

            return (isBuilding(b), newest_complete_time, oldest_request_time)

        yield async_sort(builders, key)
        return builders

    c['prioritizeBuilders'] = prioritizeBuilders


.. index:: Builds; priority


.. _Build-Priority-Functions:

Build Priority Functions
------------------------

When a builder has multiple pending build requests, it uses a ``nextBuild`` function to decide
which build it should start first. This function is given two parameters: the :class:`Builder`, and
a list of :class:`BuildRequest` objects representing pending build requests.

A simple function to prioritize release builds over other builds might look like this:

.. code-block:: python

   def nextBuild(bldr, requests):
       for r in requests:
           if r.source.branch == 'release':
               return r
       return requests[0]

If some non-immediate result must be calculated, the ``nextBuild`` function can also return a Deferred:

.. code-block:: python

    def nextBuild(bldr, requests):
        d = get_request_priorities(requests)
        def pick(priorities):
            if requests:
                return sorted(zip(priorities, requests))[0][1]
        d.addCallback(pick)
        return d

The ``nextBuild`` function is passed as parameter to :class:`BuilderConfig`:

.. code-block:: python

    ... BuilderConfig(..., nextBuild=nextBuild, ...) ...

.. index:: Schedulers; priority


.. _Scheduler-Priority-Functions:

Scheduler Priority Functions
----------------------------
When a :class:`Scheduler` is creating a a new :class:`BuildRequest` from a (list of)
:class:`Change` (s),it is possible to set the :class:`BuildRequest` priority. This can either be an
integer or a function, which receives a list of builder names and a dictionary of :class:`Change`,
grouped by their codebase.

A simple implementation might look like this:

.. code-block:: python

   def scheduler_priority(builderNames, changesByCodebase):
        priority = 0

        for codebase, changes in changesByCodebase.items():
            for chg in changes:
                if chg["branch"].startswith("dev/"):
                        priority = max(priority, 0)
                elif chg["branch"].startswith("bugfix/"):
                        priority = max(priority, 5)
                elif chg["branch"] == "main":
                        priority = max(priority, 10)

        return priority

The priority function/integer can be passed as a parameter to :class:`Scheduler`:

.. code-block:: python

   ... schedulers.SingleBranchScheduler(..., priority=scheduler_priority, ...) ...
