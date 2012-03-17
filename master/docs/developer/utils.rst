Utilities
=========

.. py:module:: buildbot.util

Several small utilities are available at the top-level :mod:`buildbot.util`
package.

.. py:function:: naturalSort(list)

    :param list: list of strings
    :returns: sorted strings

    This function sorts strings "naturally", with embedded numbers sorted
    numerically.  This ordering is good for objects which might have a numeric
    suffix, e.g., ``winslave1``, ``winslave2``

.. py:function:: formatInterval(interval)

    :param interval: duration in seconds
    :returns: human-readable (English) equivalent

    This function will return a human-readable string describing a length of
    time, given a number of seconds.

.. py:class:: ComparableMixin

    This mixin class adds comparability to a subclass.  Use it like this::

        class Widget(FactoryProduct, ComparableMixin):
            compare_attrs = [ 'radius', 'thickness' ]
            # ...

    Any attributes not in ``compare_attrs`` will not be considered when
    comparing objects.  This is particularly useful in implementing buildbot's
    reconfig logic, where a simple comparison between the new and existing objects
    can determine whether the new object should replace the existing object.

.. py:function:: safeTranslate(str)

    :param str: input string
    :returns: safe version of the input

    This function will filter out some inappropriate characters for filenames;
    it is suitable for adapting strings from the configuration for use as
    filenames.  It is not suitable for use with strings from untrusted sources.

.. py:function:: deferredLocked(lock)

    :param lock: a ``DeferredLock`` instance or a string naming one

    This is a decorator to wrap an event-driven method (one returning a
    ``Deferred``) in an acquire/release pair of a designated ``DeferredLock``.
    For simple functions with a static lock, this is as easy as::

        someLock = defer.DeferredLock()
        @util.deferredLocked(someLock)
        def someLockedFunction():
            # ..
            return d

    For class methods which must access a lock that is an instance attribute, the
    lock can be specified by a string, which will be dynamically resolved to the
    specific instance at runtime::

        def __init__(self):
            self.someLock = defer.DeferredLock()

        @util.deferredLocked('someLock')
        def someLockedFunction():
            # ..
            return d

.. py:function:: epoch2datetime(epoch)

    :param epoch: an epoch time (integer)
    :returns: equivalent datetime object

    Convert a UNIX epoch timestamp to a Python datetime object, in the UTC
    timezone.  Note that timestamps specify UTC time (modulo leap seconds and a
    few other minor details).

.. py:function:: datetime2epoch(datetime)

    :param datetime: a datetime object
    :returns: equivalent epoch time (integer)

    Convert an arbitrary Python datetime object into a UNIX epoch timestamp.

.. py:data:: UTC

    A ``datetime.tzinfo`` subclass representing UTC time.  A similar class has
    finally been added to Python in version 3.2, but the implementation is simple
    enough to include here.  This is mostly used in tests to create timezone-aware
    datetime objects in UTC::

        dt = datetime.datetime(1978, 6, 15, 12, 31, 15, tzinfo=UTC)

.. py:function:: diffSets(old, new)

    :param old: old set
    :type old: set or iterable
    :param new: new set
    :type new: set or iterable
    :returns: a tuple, (removed, added)

    This function compares two sets of objects, returning elements that were
    added and elements that were removed.  This is largely a convenience
    function for reconfiguring services.

.. py:function:: makeList(input)

    :param input: a thing
    :returns: a list of zero or more things

    This function is intended to support the many places in Buildbot where the
    user can specify either a string or a list of strings, but the
    implementation wishes to always consider lists.  It converts any string to
    a single-element list, ``None`` to an empty list, and any iterable to a
    list.  Input lists are copied, avoiding aliasing issues.

.. py:function:: now()

    :returns: epoch time (integer)

    Return the current time, using either ``reactor.seconds`` or
    ``time.time()``.

.. py:function:: flatten(list)

    :param list: potentially nested list
    :returns: flat list

    Flatten nested lists into a list containing no other lists.  For example:

    .. code-block:: none

        >>> flatten([ [  1, 2 ], 3, [ [ 4 ] ] ])
        [ 1, 2, 3, 4 ]

    Note that this looks strictly for lists -- tuples, for example, are not
    flattened.

.. py:function:: none_or_str(obj)

    :param obj: input value
    :returns: string or ``None``

    If ``obj`` is not None, return its string representation.

.. py:data:: NotABranch

    This is a sentinel value used to indicate that no branch is specified.  It
    is necessary since schedulers and change sources consider ``None`` a valid
    name for a branch.  This is generally used as a default value in a method
    signature, and then tested against with ``is``::

        if branch is NotABranch:
            pass # ...

buildbot.util.lru
~~~~~~~~~~~~~~~~~

.. py:module:: buildbot.util.lru

.. py:class:: AsyncLRUCache(miss_fn, max_size=50):

    :param miss_fn: function to call, with key as parameter, for cache misses.
        This function *must* return a Deferred.
    :param max_size: maximum number of objects in the cache.

    This is a simple least-recently-used cache.  When the cache grows beyond
    the maximum size, the least-recently used items will be automatically
    removed from the cache.

    This cache is designed to control memory usage by minimizing duplication of
    objects, while avoiding unnecessary re-fetching of the same rows from the
    database.

    Asynchronous locking is used to ensure that in the common case of multiple
    concurrent requests for the same key, only one fetch is performed.

    All values are also stored in a weak valued dictionary, even after they
    have expired from the cache.  This allows values that are used elsewhere in
    Buildbot to "stick" in the cache in case they are needed by another
    component.  Weak references cannot be used for some types, so these types
    are not compatible with this class.  Note that dictionaries can be weakly
    referenced if they are an instance of a subclass of ``dict``.

    If the result of the ``miss_fn`` is ``None``, then the value is not cached;
    this is intended to avoid caching negative results.

    This is based on `Raymond Hettinger's implementation
    <http://code.activestate.com/recipes/498245-lru-and-lfu-cache-decorators/>`_,
    licensed under the PSF license, which is GPL-compatiblie.

    .. py:attribute:: hits

        cache hits so far

    .. py:attribute:: refhits

        cache misses found in the weak ref dictionary, so far

    .. py:attribute:: misses

        cache misses leading to re-fetches, so far

    .. py:attribute:: max_size

        maximum allowed size of the cache

    .. py:method:: get(key, \*\*miss_fn_kwargs)

        :param key: cache key
        :param miss_fn_kwargs: keyword arguments to the ``miss_fn``
        :returns: value via Deferred

        Fetch a value from the cache by key, invoking ``miss_fn(key,
        **miss_fn_kwargs)`` if the key is not in the cache.

        Any additional keyword arguments are passed to the ``miss_fn`` as
        keyword arguments; these can supply additional information relating to
        the key.  It is up to the caller to ensure that this information is
        functionally identical for each key value: if the key is already in the
        cache, the ``miss_fn`` will not be invoked, even if the keyword
        arguments differ.

    .. py:method:: put(key, value)

        :param key: key at which to place the value
        :param value: value to place there

        Update the cache with the given key and value, but only if the key is
        already in the cache.  This is intended to be used when updated values
        are available for an existing cached object, and does not record a
        reference to the key for purposes of LRU removal.

    .. py:method set_max_size(max_size)

        :param max_size: new maximum cache size

        Change the cache's maximum size.  If the size is reduced, cached
        elements will be evicted.  This method exists to support dynamic
        reconfiguration of cache sizes in a running process.

    .. py:method:: inv()

        Check invariants on the cache.  This is intended for debugging
        purposes.

buildbot.util.bbcollections
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. py:module:: buildbot.util.bbcollections

This package provides a few useful collection objects.

.. note:: This module used to be named ``collections``, but without absolute
    imports (:pep:`328`), this precluded using the standard library's
    ``collections`` module.

.. py:class:: defaultdict

    This is a clone of the Python :class:`collections.defaultdict` for use in
    Python-2.4.  In later versions, this is simply a reference to the built-in
    :class:`defaultdict`, so buildbot code can simply use
    :class:`buildbot.util.collections.defaultdict` everywhere.

.. py:class:: KeyedSets

    This is a collection of named sets.  In principal, it contains an empty set
    for every name, and you can add things to sets, discard things from sets,
    and so on. ::

        >>> ks = KeyedSets()
        >>> ks['tim']                   # get a named set
        set([])
        >>> ks.add('tim', 'friendly')   # add an element to a set
        >>> ks.add('tim', 'dexterous')
        >>> ks['tim']
        set(['friendly', 'dexterous'])
        >>> 'tim' in ks                 # membership testing
        True
        >>> 'ron' in ks
        False
        >>> ks.discard('tim', 'friendly')# discard set element
        >>> ks.pop('tim')               # return set and reset to empty
        set(['dexterous'])
        >>> ks['tim']
        set([])

    This class is careful to conserve memory space - empty sets do not occupy
    any space.

buildbot.util.eventual
~~~~~~~~~~~~~~~~~~~~~~

.. py:module:: buildbot.util.eventual

This function provides a simple way to say "please do this later".  For example::

    from buildbot.util.eventual import eventually
    def do_what_I_say(what, where):
        # ...
        return d
    eventually(do_what_I_say, "clean up", "your bedroom")

The package defines "later" as "next time the reactor has control", so this is
a good way to avoid long loops that block other activity in the reactor.

.. py:function:: eventually(cb, *args, \*\*kwargs)

    :param cb: callable to invoke later
    :param args: args to pass to ``cb``
    :param kwargs: kwargs to pass to ``cb``

    Invoke the callable ``cb`` in a later reactor turn.

    Callables given to :func:`eventually` are guaranteed to be called in the
    same order as the calls to :func:`eventually` -- writing ``eventually(a);
    eventually(b)`` guarantees that ``a`` will be called before ``b``.

    Any exceptions that occur in the callable will be logged with
    ``log.err()``.  If you really want to ignore them, provide a callable that
    catches those exceptions.

    This function returns None. If you care to know when the callable was
    run, be sure to provide a callable that notifies somebody.

.. py:function:: fireEventually(value=None)

    :param value: value with which the Deferred should fire
    :returns: Deferred

    This function returns a Deferred which will fire in a later reactor turn,
    after the current call stack has been completed, and after all other
    Deferreds previously scheduled with :py:func:`eventually`.  The returned
    Deferred will never fail.

.. py:function:: flushEventualQueue()

    :returns: Deferred

    This returns a Deferred which fires when the eventual-send queue is finally
    empty. This is useful for tests and other circumstances where it is useful
    to know that "later" has arrived.

buildbot.util.json
~~~~~~~~~~~~~~~~~~

This package is just an import of the best available JSON module.  Use it
instead of a more complex conditional import of :mod:`simplejson` or
:mod:`json`::

    from buildbot.util import json

