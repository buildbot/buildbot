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
