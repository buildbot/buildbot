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

    A point to note is that the compare_attrs list is cumulative; that is,
    when a subclass also has a compare_attrs and the parent class has a
    compare_attrs, the subclass' compare_attrs also includes the parent
    class' compare_attrs.

.. py:function:: safeTranslate(str)

    :param str: input string
    :returns: safe version of the input

    This function will filter out some inappropriate characters for filenames;
    it is suitable for adapting strings from the configuration for use as
    filenames.  It is not suitable for use with strings from untrusted sources.

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

.. py:function:: in_reactor(fn)

    This decorator will cause the wrapped function to be run in the Twisted
    reactor, with the reactor stopped when the function completes.  It returns
    the result of the wrapped function.  If the wrapped function fails, its
    traceback will be printed, the reactor halted, and ``None`` returned.

.. py:function:: asyncSleep(secs)

    Yield a deferred that will fire with no result after ``secs`` seconds.
    This is the asynchronous equivalent to ``time.sleep``, and can be useful in tests.

buildbot.util.lru
~~~~~~~~~~~~~~~~~

.. py:module:: buildbot.util.lru

.. py:class:: LRUCache(miss_fn, max_size=50):

    :param miss_fn: function to call, with key as parameter, for cache misses.
        The function should return the value associated with the key argument,
        or None if there is no value associated with the key.
    :param max_size: maximum number of objects in the cache.

    This is a simple least-recently-used cache.  When the cache grows beyond
    the maximum size, the least-recently used items will be automatically
    removed from the cache.

    This cache is designed to control memory usage by minimizing duplication of
    objects, while avoiding unnecessary re-fetching of the same rows from the
    database.

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

        Add the given key and value into the cache.  The purpose of this
        method is to insert a new value into the cache *without* invoking
        the miss_fn (e.g., to avoid unnecessary overhead).

    .. py:method set_max_size(max_size)

        :param max_size: new maximum cache size

        Change the cache's maximum size.  If the size is reduced, cached
        elements will be evicted.  This method exists to support dynamic
        reconfiguration of cache sizes in a running process.

    .. py:method:: inv()

        Check invariants on the cache.  This is intended for debugging
        purposes.

.. py:class:: AsyncLRUCache(miss_fn, max_size=50):

    :param miss_fn: This is the same as the miss_fn for class LRUCache, with
        the difference that this function *must* return a Deferred.
    :param max_size: maximum number of objects in the cache.

    This class has the same functional interface as LRUCache, but asynchronous
    locking is used to ensure that in the common case of multiple concurrent
    requests for the same key, only one fetch is performed.

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

buildbot.util.debounce
~~~~~~~~~~~~~~~~~~~~~~

.. py:module:: buildbot.util.debounce

Often, a method must be called exactly once at a time, but many events may trigger a call to the method.
A simple example is the step method :py:meth:`~buildbot.process.buildstep.BuildStep.updateSummary`.

The ``debounce.method(wait)`` decorator is the tool for the job.

.. py:function:: method(wait)

    :param wait: time to wait before invoking, in seconds

    Returns a decorator that debounces the underlying method.
    The underlying method must take no arguments (except ``self``).

    For each call to the decorated method, the underlying method will be invocation at least once within *wait* seconds (plus the time the method takes to execute).
    Calls are "debounced" during that time, meaning that multiple calls to the decorated method may result in a single invocation.

    The decorated method is an instance of :py:class:`Debouncer`, allowing it to be started and stopped.
    This is useful when the method is a part of a Buidbot service: call ``method.start()`` from ``startService`` and ``method.stop()`` from ``stopService``, handling its Deferred appropriately.

.. py:class:: Debouncer

    .. py:method:: stop()

        :returns: Deferred

        Stop the debouncer.
        While the debouncer is stopped, calls to the decorated method will be ignored.
        When the Deferred that ``stop`` returns fires, the underlying method is not executing.

    .. py:method:: start()

        Start the debouncer.
        This reverses the effects of ``stop``.
        This method can be called on a started debouncer without issues.


buildbot.util.json
~~~~~~~~~~~~~~~~~~

.. py:module:: buildbot.util.json

This package is just an import of the best available JSON module.  Use it
instead of a more complex conditional import of :mod:`simplejson` or
:mod:`json`::

    from buildbot.util import json

buildbot.util.maildir
~~~~~~~~~~~~~~~~~~~~~

.. py:module:: buildbot.util.maildir

Several Buildbot components make use of `maildirs
<http://www.courier-mta.org/maildir.html>`_ to hand off messages between
components.  On the receiving end, there's a need to watch a maildir for
incoming messages and trigger some action when one arrives.

.. py:class:: MaildirService(basedir)

        :param basedir: (optional) base directory of the maildir

    A :py:class:`MaildirService` instance watches a maildir for new messages. It
    should be a child service of some :py:class:`~twisted.application.service.MultiService` instance. When
    running, this class uses the linux dirwatcher API (if available) or polls for new
    files in the 'new' maildir subdirectory. When it discovers a new
    message, it invokes its :py:meth:`messageReceived` method.

    To use this class, subclass it and implement a more interesting
    :py:meth:`messageReceived` function.

    .. py:method:: setBasedir(basedir)

        :param basedir: base directory of the maildir

        If no ``basedir`` is provided to the constructor, this method must be
        used to set the basedir before the service starts.

    .. py:method:: messageReceived(filename)

        :param filename: unqualified filename of the new message

        This method is called with the short filename of the new message. The
        full name of the new file can be obtained with ``os.path.join(maildir,
        'new', filename)``.  The method is un-implemented in the
        :py:class:`MaildirService` class, and must be implemented in
        subclasses.

    .. py:method:: moveToCurDir(filename)

        :param filename: unqualified filename of the new message
        :returns: open file object

        Call this from :py:meth:`messageReceived` to start processing the
        message; this moves the message file to the 'cur' directory and returns
        an open file handle for it.

buildbot.util.misc
~~~~~~~~~~~~~~~~~~

.. py:module:: buildbot.util.misc

.. py:function:: deferredLocked(lock)

    :param lock: a :py:class:`twisted.internet.defer.DeferredLock` instance or
        a string naming an instance attribute containing one

    This is a decorator to wrap an event-driven method (one returning a
    ``Deferred``) in an acquire/release pair of a designated
    :py:class:`~twisted.internet.defer.DeferredLock`.  For simple functions
    with a static lock, this is as easy as::

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

.. py:class:: SerializedInvocation(method)

    This is a method wrapper that will serialize calls to an asynchronous
    method.  If a second call occurs while the first call is still executing,
    it will not begin until the first call has finished.  If multiple calls
    queue up, they will be collapsed into a single call.  The effect is that
    the underlying method is guaranteed to be called at least once after every
    call to the wrapper.

    Note that if this class is used as a decorator on a method, it will
    serialize invocations across all class instances.  For synchronization
    specific to each instance, wrap the method in the constructor::

        def __init__(self):
            self.someMethod = SerializedInovcation(self.someMethod)

    Tests can monkey-patch the ``_quiet`` method of the class to be notified
    when all planned invocations are complete.

buildbot.util.netstrings
~~~~~~~~~~~~~~~~~~~~~~~~

.. py:module:: buildbot.util.netstrings

Similar to maildirs, `netstrings <http://cr.yp.to/proto/netstrings.txt>`_ are
used occasionally in Buildbot to encode data for interchange.  While Twisted
supports a basic netstring receiver protocol, it does not have a simple way to
apply that to a non-network situation.

.. py:class:: NetstringParser

    This class parses strings piece by piece, either collecting the accumulated
    strings or invoking a callback for each one.

    .. py:method:: feed(data)

        :param data: a portion of netstring-formatted data
        :raises: :py:exc:`twisted.protocols.basic.NetstringParseError`

        Add arbitrarily-sized ``data`` to the incoming-data buffer.  Any
        complete netstrings will trigger a call to the
        :py:meth:`stringReceived` method.

        Note that this method (like the Twisted class it is based on) cannot
        detect a trailing partial netstring at EOF - the data will be silently
        ignored.

    .. py:method:: stringReceived(string):

        :param string: the decoded string

        This method is called for each decoded string as soon as it is read
        completely.  The default implementation appends the string to the
        :py:attr:`strings` attribute, but subclasses can do anything.

    .. py:attribute:: strings

        The strings decoded so far, if :py:meth:`stringReceived` is not
        overridden.

buildbot.util.sautils
~~~~~~~~~~~~~~~~~~~~~

.. py:module:: buildbot.util.sautils

This module contains a few utilities that are not included with SQLAlchemy.

.. py:class:: InsertFromSelect(table, select)

    :param table: table into which insert should be performed
    :param select: select query from which data should be drawn

    This class is taken directly from SQLAlchemy's `compiler.html
    <http://www.sqlalchemy.org/docs/core/compiler.html#compiling-sub-elements-of-a-custom-expression-construct>`_,
    and allows a Pythonic representation of ``INSERT INTO .. SELECT ..``
    queries.

.. py:function:: sa_version()

    Return a 3-tuple representing the SQLAlchemy version.  Note that older
    versions that did not have a ``__version__`` attribute are represented by
    ``(0,0,0)``.

buildbot.util.subscription
~~~~~~~~~~~~~~~~~~~~~~~~~~

The classes in the :py:mod:`buildbot.util.subscription` module are used for
master-local subscriptions.  In the near future, all uses of this module will
be replaced with message-queueing implementations that allow subscriptions and
subscribers to span multiple masters.

buildbot.util.croniter
~~~~~~~~~~~~~~~~~~~~~~

This module is a copy of https://github.com/taichino/croniter, and provides
support for converting cron-like time specifications into actual times.

buildbot.util.state
~~~~~~~~~~~~~~~~~~~
.. py:module:: buildbot.util.state

The classes in the :py:mod:`buildbot.util.subscription` module are used for dealing with object state stored in the database.

.. py:class:: StateMixin

    This class provides helper methods for accessing the object state stored in the database.

    .. py:attribute:: name

         This must be set to the name to be used to identify this object in the database.

    .. py:attribute:: master

         This must point to the :py:class:`BuildMaster` object.

    .. py:method:: getState(name, default)

        :param name: name of the value to retrieve
        :param default: (optional) value to return if `name` is not present
        :returns: state value via a Deferred
        :raises KeyError: if `name` is not present and no default is given
        :raises TypeError: if JSON parsing fails

        Get a named state value from the object's state.

    .. py:method:: getState(name, value)

        :param name: the name of the value to change
        :param value: the value to set - must be a JSONable object
        :param returns: Deferred
        :raises TypeError: if JSONification fails

        Set a named state value in the object's persistent state.
        Note that value must be json-able.

buildbot.util.identifiers
~~~~~~~~~~~~~~~~~~~~~~~~~

.. py:module:: buildbot.util.identifiers

This module makes it easy to manipulate identifiers.

.. py:function:: isIdentifier(maxLength, object)

    :param maxLength: maximum length of the identifier
    :param object: object to test for identifier-ness
    :returns: boolean

    Is object an identifier?

.. py:function:: forceIdentifier(maxLength, str)

    :param maxLength: maximum length of the identifier
    :param str: string to coerce to an identifier
    :returns: identifer of maximum length ``maxLength``

    Coerce a string (assuming ASCII for bytestrings) into an identifier.
    This method will replace any invalid characters with ``_`` and truncate to the given length.

.. py:function:: incrementIdentifier(maxLength, str)

    :param maxLength: maximum length of the identifier
    :param str: identifier to increment
    :returns: identifer of maximum length ``maxLength``
    :raises: ValueError if no suitable identifier can be constructed

    "Increment" an identifier by adding a numeric suffix, while keeping the total length limited.
    This is useful when selecting a unique identifier for an object.
    Maximum-length identifiers like ``_999999`` cannot be incremented and will raise :py:exc:`ValueError`.
