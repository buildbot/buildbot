Utilities
=========

Several small utilities are available at the top-level :mod:`buildbot.util`
package.  As always, see the API documentation for more information.

:func:`naturalSort`
    This function sorts strings "naturally", with embedded numbers sorted
    numerically.  This ordering is good for objects which might have a numeric
    suffix, e.g., ``winslave1``, ``winslave2``

:func:`formatInterval`
    This function will return a human-readable string describing a length of time,
    given a number of seconds.

:class:`ComparableMixin`
    This mixin class adds comparability to a subclass.  Use it like this::

        class Widget(FactoryProduct, ComparableMixin):
            compare_attrs = [ 'radius', 'thickness' ]
            # ...

    Any attributes not in ``compare_attrs`` will not be considered when
    comparing objects.  This is particularly useful in implementing buildbot's
    reconfig logic, where a simple comparison between the new and existing objects
    can determine whether the new object should replace the existing object.

:func:`safeTranslate`
    This function will filter out some inappropriate characters for filenames; it
    is suitable for adapting strings from the configuration for use as filenames.
    It is not suitable for use with strings from untrusted sources.

:class:`AsyncLRUCache`
    This is a simple least-recently-used cache.  Its constructor takes a maximum
    size.  When the cache grows beyond this size, the least-recently used items
    will be automatically removed from the cache.  The class has a
    :meth:`get` method that takes a key and a function to call (with
    the key) when the key is not in the cache.  Both :meth:`get` and
    the miss function return Deferreds.

``deferredLocked``

    This is a decorator to wrap an event-driven method (one returning
    a ``Deferred``) in an acquire/release pair of a designated
    ``DeferredLock``.  For simple functions with a static lock, this
    is as easy as::


        someLock = defer.DeferredLock()
        @util.deferredLocked(someLock)
        def someLockedFunction(..):
            # ..
            return d

    for class methods which must access a lock that is an instance attribute, the
    lock can be specified by a string, which will be dynamically resolved to the
    specific instance at runtime::


        def __init__(self):
            self.someLock = defer.DeferredLock()

        @util.deferredLocked('someLock')
            def someLockedFunction(..):
            # ..
            return d

:func:`epoch2datetime`

    Convert a UNIX epoch timestamp (an integer) to a Python datetime
    object, in the UTC timezone.  Note that timestamps specify UTC
    time (modulo leap seconds and a few other minor details).

:func:`datetime2epoch`

    Convert an arbitrary Python datetime object into a UNIX epoch timestamp.

``UTC``

    A ``datetime.tzinfo`` subclass representing UTC time.  A similar class has
    finally been added to Python in version 3.2, but the implementation is simple
    enough to include here.  This is mostly used in tests to create timezeon-aware
    datetime objects in UTC::

        dt = datetime.datetime(1978, 6, 15, 12, 31, 15, tzinfo=UTC)

buildbot.util.bbcollections
~~~~~~~~~~~~~~~~~~~~~~~~~~~

This package provides a few useful collection objects.

.. note:: It used to be named ``collections``, but without absolute
   imports (:pep:`328`), this precluded using the standard library's
   ``collections`` module.

For compatibility, it provides a clone of the Python
:class:`collections.defaultdict` for use in Python-2.4.  In later versions, this
is simply a reference to the built-in :class:`defaultdict`, so buildbot code can
simply use :class:`buildbot.util.collections.defaultdict` everywhere.

It also provides a :class:`KeyedSets` class that can represent any numbers of
sets, keyed by name (or anything hashable, really).  The object is specially
tuned to contain many different keys over its lifetime without wasting memory.
See the docstring for more information.

buildbot.util.eventual
~~~~~~~~~~~~~~~~~~~~~~

This package provides a simple way to say "please do this later"::

    from buildbot.util.eventual import eventually
    def do_what_I_say(what, where):
        # ...
    eventually(do_what_I_say, "clean up", "your bedroom")

The package defines "later" as "next time the reactor has control", so this is
a good way to avoid long loops that block other activity in the reactor.
Callables given to :func:`eventually` are guaranteed to be called in the same
order as the calls to :func:`eventually`.  Any errors from the callable are
logged, but will not affect other callables.

If you need a deferred that will fire "later", use :func:`fireEventually`.  This
function returns a deferred that will not errback.

buildbot.util.json
~~~~~~~~~~~~~~~~~~

This package is just an import of the best available JSON module.  Use it
instead of a more complex conditional import of :mod:`simplejson` or
:mod:`json`.

.. _The-Database:

