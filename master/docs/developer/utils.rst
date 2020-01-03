Utilities
=========

.. py:module:: buildbot.util

Several small utilities are available at the top-level :mod:`buildbot.util` package.

.. py:function:: naturalSort(list)

    :param list: list of strings
    :returns: sorted strings

    This function sorts strings "naturally", with embedded numbers sorted numerically.
    This ordering is good for objects which might have a numeric suffix, e.g., ``winworker1``, ``winworker2``

.. py:function:: formatInterval(interval)

    :param interval: duration in seconds
    :returns: human-readable (English) equivalent

    This function will return a human-readable string describing a length of time, given a number of seconds.

.. py:class:: ComparableMixin

    This mixin class adds comparability to a subclass.
    Use it like this:

    .. code-block:: python

        class Widget(FactoryProduct, ComparableMixin):
            compare_attrs = ( 'radius', 'thickness' )
            # ...

    Any attributes not in ``compare_attrs`` will not be considered when comparing objects.
    This is used to implement Buildbot's reconfig logic, where a comparison between the new and existing objects is used to determine whether the new object should replace the existing object.
    If the comparison shows the objects to be equivalent, then the old object is left in place.
    If they differ, the old object is removed from the buildmaster and the new object added.

    For use in configuration objects (schedulers, changesources, etc.), include any attributes which are set in the constructor based on the user's configuration.
    Be sure to also include the superclass's list, e.g.:

    .. code-block:: python

        class MyScheduler(base.BaseScheduler):
            compare_attrs = base.BaseScheduler.compare_attrs + ('arg1', 'arg2')


    A point to note is that the compare_attrs list is cumulative; that is, when a subclass also has a compare_attrs and the parent class has a compare_attrs, the subclass' compare_attrs also includes the parent class' compare_attrs.

    This class also implements the :py:class:`buildbot.interfaces.IConfigured` interface.
    The configuration is automatically generated, being the dict of all ``compare_attrs``.

.. py:function:: safeTranslate(str)

    :param str: input string
    :returns: safe version of the input

    This function will filter out some inappropriate characters for filenames; it is suitable for adapting strings from the configuration for use as filenames.
    It is not suitable for use with strings from untrusted sources.

.. py:function:: epoch2datetime(epoch)

    :param epoch: an epoch time (integer)
    :returns: equivalent datetime object

    Convert a UNIX epoch timestamp to a Python datetime object, in the UTC timezone.
    Note that timestamps specify UTC time (modulo leap seconds and a few other minor details).
    If the argument is None, returns None.

.. py:function:: datetime2epoch(datetime)

    :param datetime: a datetime object
    :returns: equivalent epoch time (integer)

    Convert an arbitrary Python datetime object into a UNIX epoch timestamp.
    If the argument is None, returns None.

.. py:data:: UTC

    A ``datetime.tzinfo`` subclass representing UTC time.
    A similar class has finally been added to Python in version 3.2, but the implementation is simple enough to include here.
    This is mostly used in tests to create timezone-aware datetime objects in UTC:

    .. code-block:: python

        dt = datetime.datetime(1978, 6, 15, 12, 31, 15, tzinfo=UTC)

.. py:function:: diffSets(old, new)

    :param old: old set
    :type old: set or iterable
    :param new: new set
    :type new: set or iterable
    :returns: a tuple, (removed, added)

    This function compares two sets of objects, returning elements that were added and elements that were removed.
    This is largely a convenience function for reconfiguring services.

.. py:function:: makeList(input)

    :param input: a thing
    :returns: a list of zero or more things

    This function is intended to support the many places in Buildbot where the user can specify either a string or a list of strings, but the implementation wishes to always consider lists.
    It converts any string to a single-element list, ``None`` to an empty list, and any iterable to a list.
    Input lists are copied, avoiding aliasing issues.

.. py:function:: now()

    :returns: epoch time (integer)

    Return the current time, using either ``reactor.seconds`` or ``time.time()``.

.. py:function:: flatten(list, [types])

    :param list: potentially nested list
    :param types: An optional iterable of the types to flatten.
        By default, if unspecified, this flattens both lists and tuples
    :returns: flat list

    Flatten nested lists into a list containing no other lists. For example:

    .. code-block:: python

        >>> flatten([ [  1, 2 ], 3, [ [ 4 ], 5 ] ])
        [ 1, 2, 3, 4, 5 ]

    Both lists and tuples are looked at by default.

.. py:function:: flattened_iterator(list, [types])

    :param list: potentially nested list
    :param types: An optional iterable of the types to flatten.
        By default, if unspecified, this flattens both lists and tuples.
    :returns: iterator over every element that isn't in types

    Returns a generator that doesn't yield any lists/tuples.  For example:

    .. code-block:: none

        >>> for x in flattened_iterator([ [  1, 2 ], 3, [ [ 4 ] ] ]):
        >>>     print x
        1
        2
        3
        4

     Use this for extremely large lists to keep memory-usage down and improve performance when you only need to iterate once.

.. py:function:: none_or_str(obj)

    :param obj: input value
    :returns: string or ``None``

    If ``obj`` is not None, return its string representation.

.. py:function:: bytes2unicode(bytestr, encoding='utf-8', errors='strict'):

    :param bytestr: bytes
    :param encoding: unicode encoding to pass to :py:func:`str.encode`, default ``utf-8``.
    :param errors: error handler to pass to :py:func:`str.encode`, default ``strict``.
    :returns: string as unicode

    This function is intended to convert bytes to unicode for user convenience.
    If given a bytestring, it returns the string decoded using ``encoding``.
    If given a unicode string, it returns it directly.

.. py:function:: string2boolean(str):

    :param str: string
    :raises KeyError:
    :returns: boolean

    This function converts a string to a boolean.
    It is intended to be liberal in what it accepts: case-insensitive, "true", "on", "yes", "1", etc.
    It raises :py:exc:`KeyError` if the value is not recognized.

.. py:function:: toJson(obj):

    :param obj: object
    :returns: UNIX epoch timestamp

    This function is a helper for json.dump, that allows to convert non-json able objects to json.
    For now it supports converting datetime.datetime objects to unix timestamp.

.. py:data:: NotABranch

    This is a sentinel value used to indicate that no branch is specified.
    It is necessary since schedulers and change sources consider ``None`` a valid name for a branch.
    This is generally used as a default value in a method signature, and then tested against with ``is``:

    .. code-block:: python

        if branch is NotABranch:
            pass # ...

.. py:function:: in_reactor(fn)

    This decorator will cause the wrapped function to be run in the Twisted reactor, with the reactor stopped when the function completes.
    It returns the result of the wrapped function.
    If the wrapped function fails, its traceback will be printed, the reactor halted, and ``None`` returned.

.. py:function:: asyncSleep(secs, reactor=None)

    Yield a deferred that will fire with no result after ``secs`` seconds.
    This is the asynchronous equivalent to ``time.sleep``, and can be useful in tests.
    In case a custom reactor is used, the ``reactor`` parameter may be set.
    By default, ``twisted.internet.reactor`` is used.

.. py:function:: stripUrlPassword(url)

    :param url: a URL
    :returns: URL with any password component replaced with ``xxxx``

    Sanitize a URL; use this before logging or displaying a DB URL.

.. py:function:: join_list(maybe_list)

    :param maybe_list: list, tuple, byte string, or unicode
    :returns: unicode

    If ``maybe_list`` is a list or tuple, join it with spaces, casting any strings into unicode using :py:func:`bytes2unicode`.
    This is useful for configuration parameters that may be strings or lists of strings.

.. py:class:: Notifier():

    This is a helper for firing multiple deferreds with the same result.

    .. py:method:: wait()

        Return a deferred that will fire when when the notifier is notified.

    .. py:method:: notify(value)

        Fire all the outstanding deferreds with the given value.

.. py:function:: giturlparse(url)

    :param url: a git url
    :returns: a :py:class:`GitUrl` with results of parsed url

    This function is intended to help various components to parse git urls.
    It helps to find the ``<owner>/<repo>`` of a git repository url coming from a change, in order to call urls.
    ``owner`` and ``repo`` is a common scheme for identifying git repository between various git hosting services like GitHub, GitLab, BitBucket, etc.
    Each service have their own naming for similar things, but we choose to use the GitHub naming as a de-facto standard.
    To simplify implementation, the parser is accepting invalid urls, but it should always parse valid urls correctly.
    The unit tests in ``test_util_giturlparse.py`` is the references of what the parser is accepting.
    Please feel free to update the parser and unit tests

    Example use:

    .. code-block:: python

            from buildbot.util import giturlparse
            repourl = giturlparse(sourcestamp['repository'])
            repoOwner = repourl.owner
            repoName = repourl.repo

.. py:class:: GitUrl():

    .. py:attribute:: proto

        The protocol of the url

    .. py:attribute:: user

        The user of the url (as in ``user@domain``)

    .. py:attribute:: domain

        The domain part of the url

    .. py:attribute:: port

        The optional port of the url

    .. py:attribute:: owner

        The owner of the repository (in case of GitLab might be a nested group, i.e contain ``/``, e.g ``repo/subrepo/subsubrepo``)

    .. py:attribute:: repo

        The owner of the repository (in case of GitLab might be a nested group, i.e contain ``/``)


:py:mod:`buildbot.util.lru`
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. py:module:: buildbot.util.lru

.. py:class:: LRUCache(miss_fn, max_size=50):

    :param miss_fn: function to call, with key as parameter, for cache misses.
        The function should return the value associated with the key argument, or None if there is no value associated with the key.
    :param max_size: maximum number of objects in the cache.

    This is a simple least-recently-used cache.
    When the cache grows beyond the maximum size, the least-recently used items will be automatically removed from the cache.

    This cache is designed to control memory usage by minimizing duplication of objects, while avoiding unnecessary re-fetching of the same rows from the database.

    All values are also stored in a weak valued dictionary, even after they have expired from the cache.
    This allows values that are used elsewhere in Buildbot to "stick" in the cache in case they are needed by another component.
    Weak references cannot be used for some types, so these types are not compatible with this class.
    Note that dictionaries can be weakly referenced if they are an instance of a subclass of ``dict``.

    If the result of the ``miss_fn`` is ``None``, then the value is not cached; this is intended to avoid caching negative results.

    This is based on `Raymond Hettinger's implementation <http://code.activestate.com/recipes/498245-lru-and-lfu-cache-decorators/>`_, licensed under the PSF license, which is GPL-compatible.

    .. py:attribute:: hits

        cache hits so far

    .. py:attribute:: refhits

        cache misses found in the weak ref dictionary, so far

    .. py:attribute:: misses

        cache misses leading to re-fetches, so far

    .. py:attribute:: max_size

        maximum allowed size of the cache

    .. py:method:: get(key, **miss_fn_kwargs)

        :param key: cache key
        :param miss_fn_kwargs: keyword arguments to the ``miss_fn``
        :returns: value via Deferred

        Fetch a value from the cache by key, invoking ``miss_fn(key, **miss_fn_kwargs)`` if the key is not in the cache.

        Any additional keyword arguments are passed to the ``miss_fn`` as keyword arguments; these can supply additional information relating to the key.
        It is up to the caller to ensure that this information is functionally identical for each key value: if the key is already in the cache, the ``miss_fn`` will not be invoked, even if the keyword arguments differ.

    .. py:method:: put(key, value)

        :param key: key at which to place the value
        :param value: value to place there

        Add the given key and value into the cache.
        The purpose of this method is to insert a new value into the cache *without* invoking the miss_fn (e.g., to avoid unnecessary overhead).

    .. py:method set_max_size(max_size)

        :param max_size: new maximum cache size

        Change the cache's maximum size.
        If the size is reduced, cached elements will be evicted.
        This method exists to support dynamic reconfiguration of cache sizes in a running process.

    .. py:method:: inv()

        Check invariants on the cache.
        This is intended for debugging purposes.

.. py:class:: AsyncLRUCache(miss_fn, max_size=50):

    :param miss_fn: This is the same as the miss_fn for class LRUCache, with the difference that this function *must* return a Deferred.
    :param max_size: maximum number of objects in the cache.

    This class has the same functional interface as LRUCache, but asynchronous locking is used to ensure that in the common case of multiple concurrent requests for the same key, only one fetch is performed.

:py:mod:`buildbot.util.bbcollections`
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. py:module:: buildbot.util.bbcollections

This package provides a few useful collection objects.

.. note::

    This module used to be named ``collections``, but without absolute imports (:pep:`328`), this precluded using the standard library's ``collections`` module.

.. py:class:: defaultdict

    This is a clone of the Python :class:`collections.defaultdict` for use in Python-2.4.
    In later versions, this is simply a reference to the built-in :class:`defaultdict`, so Buildbot code can simply use :class:`buildbot.util.collections.defaultdict` everywhere.

.. py:class:: KeyedSets

    This is a collection of named sets.
    In principal, it contains an empty set for every name, and you can add things to sets, discard things from sets, and so on.

    .. code-block:: python

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

    This class is careful to conserve memory space - empty sets do not occupy any space.

:py:mod:`buildbot.util.eventual`
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. py:module:: buildbot.util.eventual

This function provides a simple way to say "please do this later".
For example

.. code-block:: python

    from buildbot.util.eventual import eventually
    def do_what_I_say(what, where):
        # ...
        return d
    eventually(do_what_I_say, "clean up", "your bedroom")

The package defines "later" as "next time the reactor has control", so this is a good way to avoid long loops that block other activity in the reactor.

.. py:function:: eventually(cb, *args, **kwargs)

    :param cb: callable to invoke later
    :param args: args to pass to ``cb``
    :param kwargs: kwargs to pass to ``cb``

    Invoke the callable ``cb`` in a later reactor turn.

    Callables given to :func:`eventually` are guaranteed to be called in the same order as the calls to :func:`eventually` -- writing ``eventually(a); eventually(b)`` guarantees that ``a`` will be called before ``b``.

    Any exceptions that occur in the callable will be logged with ``log.err()``.
    If you really want to ignore them, provide a callable that catches those exceptions.

    This function returns None.
    If you care to know when the callable was run, be sure to provide a callable that notifies somebody.

.. py:function:: fireEventually(value=None)

    :param value: value with which the Deferred should fire
    :returns: Deferred

    This function returns a Deferred which will fire in a later reactor turn, after the current call stack has been completed, and after all other Deferreds previously scheduled with :py:func:`eventually`.
    The returned Deferred will never fail.

.. py:function:: flushEventualQueue()

    :returns: Deferred

    This returns a Deferred which fires when the eventual-send queue is finally empty.
    This is useful for tests and other circumstances where it is useful to know that "later" has arrived.

:py:mod:`buildbot.util.debounce`
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. py:module:: buildbot.util.debounce

It's often necessary to perform some action in response to a particular type of event.
For example, steps need to update their status after updates arrive from the worker.
However, when many events arrive in quick succession, it's more efficient to only perform the action once, after the last event has occurred.

The ``debounce.method(wait)`` decorator is the tool for the job.

.. py:function:: method(wait)

    :param wait: time to wait before invoking, in seconds
    :param get_reactor: A callable that takes the underlying instance and returns the reactor to use. Defaults to ``instance.master.reactor``.

    Returns a decorator that debounces the underlying method.
    The underlying method must take no arguments (except ``self``).

    For each call to the decorated method, the underlying method will be invoked at least once within *wait* seconds (plus the time the method takes to execute).
    Calls are "debounced" during that time, meaning that multiple calls to the decorated method will result in a single invocation.

    .. note::

        This functionality is similar to Underscore's ``debounce``, except that the Underscore method resets its timer on every call.

    The decorated method is an instance of :py:class:`Debouncer`, allowing it to be started and stopped.
    This is useful when the method is a part of a Buildbot service: call ``method.start()`` from ``startService`` and ``method.stop()`` from ``stopService``, handling its Deferred appropriately.

.. py:class:: Debouncer

    .. py:method:: stop()

        :returns: Deferred

        Stop the debouncer.
        While the debouncer is stopped, calls to the decorated method will be ignored.
        If a call is pending when ``stop`` is called, that call will occur immediately.
        When the Deferred that ``stop`` returns fires, the underlying method is not executing.

    .. py:method:: start()

        Start the debouncer.
        This reverses the effects of ``stop``.
        This method can be called on a started debouncer without issues.

:py:mod:`buildbot.util.poll`
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. py:module:: buildbot.util.poll

Many Buildbot services perform some periodic, asynchronous operation.
Change sources, for example, contact the repositories they monitor on a regular basis.
The tricky bit is, the periodic operation must complete before the service stops.

The ``@poll.method`` decorator makes this behavior easy and reliable.

.. py:function:: method

    This decorator replaces the decorated method with a :py:class:`Poller` instance configured to call the decorated method periodically.
    The poller is initially stopped, so periodic calls will not begin until its ``start`` method is called.
    The start polling interval is specified when the poller is started.

    If the decorated method fails or raises an exception, the Poller logs the error and re-schedules the call for the next interval.

    If a previous invocation of the method has not completed when the interval expires, then the next invocation is skipped and the interval timer starts again.

    A common idiom is to call ``start`` and ``stop`` from ``startService`` and ``stopService``:

    .. code-block:: python

        class WatchThings(object):

            @poll.method
            def watch(self):
                d = self.beginCheckingSomething()
                return d

            def startService(self):
                self.watch.start(interval=self.pollingInterval, now=False)

            def stopService(self):
                return self.watch.stop()


.. py:class:: Poller

    .. py:method:: start(interval=N, now=False)

        :param interval: time, in seconds, between invocations
        :param now: if true, call the decorated method immediately on startup.

        Start the poller.

    .. py:method:: stop()

        :returns: Deferred

        Stop the poller.
        The returned Deferred fires when the decorated method is complete.

    .. py:method:: __call__()

        Force a call to the decorated method now.
        If the decorated method is currently running, another call will begin as soon as it completes.

:py:mod:`buildbot.util.maildir`
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. py:module:: buildbot.util.maildir

Several Buildbot components make use of `maildirs <http://www.courier-mta.org/maildir.html>`_ to hand off messages between components.
On the receiving end, there's a need to watch a maildir for incoming messages and trigger some action when one arrives.

.. py:class:: MaildirService(basedir)

        :param basedir: (optional) base directory of the maildir

    A :py:class:`MaildirService` instance watches a maildir for new messages.
    It should be a child service of some :py:class:`~twisted.application.service.MultiService` instance.
    When running, this class uses the linux dirwatcher API (if available) or polls for new files in the 'new' maildir subdirectory.
    When it discovers a new message, it invokes its :py:meth:`messageReceived` method.

    To use this class, subclass it and implement a more interesting :py:meth:`messageReceived` function.

    .. py:method:: setBasedir(basedir)

        :param basedir: base directory of the maildir

        If no ``basedir`` is provided to the constructor, this method must be used to set the basedir before the service starts.

    .. py:method:: messageReceived(filename)

        :param filename: unqualified filename of the new message

        This method is called with the short filename of the new message.
        The full name of the new file can be obtained with ``os.path.join(maildir, 'new', filename)``.
        The method is un-implemented in the :py:class:`MaildirService` class, and must be implemented in subclasses.

    .. py:method:: moveToCurDir(filename)

        :param filename: unqualified filename of the new message
        :returns: open file object

        Call this from :py:meth:`messageReceived` to start processing the message; this moves the message file to the 'cur' directory and returns an open file handle for it.

:py:mod:`buildbot.util.misc`
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. py:module:: buildbot.util.misc

.. py:function:: deferredLocked(lock)

    :param lock: a :py:class:`twisted.internet.defer.DeferredLock` instance or a string naming an instance attribute containing one

    This is a decorator to wrap an event-driven method (one returning a ``Deferred``) in an acquire/release pair of a designated :py:class:`~twisted.internet.defer.DeferredLock`.
    For simple functions with a static lock, this is as easy as:

    .. code-block:: python

        someLock = defer.DeferredLock()

        @util.deferredLocked(someLock)
        def someLockedFunction():
            # ..
            return d

    For class methods which must access a lock that is an instance attribute, the lock can be specified by a string, which will be dynamically resolved to the specific instance at runtime:

    .. code-block:: python

        def __init__(self):
            self.someLock = defer.DeferredLock()

        @util.deferredLocked('someLock')
        def someLockedFunction():
            # ..
            return d

.. py:function:: cancelAfter(seconds, deferred)

    :param seconds: timeout in seconds
    :param deferred: deferred to cancel after timeout expires
    :returns: the deferred passed to the function

    Cancel the given deferred after the given time has elapsed, if it has not already been fired.
    Whent his occurs, the deferred's errback will be fired with a :py:class:`twisted.internet.defer.CancelledError` failure.

:py:mod:`buildbot.util.netstrings`
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. py:module:: buildbot.util.netstrings

Similar to maildirs, `netstrings <http://cr.yp.to/proto/netstrings.txt>`_ are used occasionally in Buildbot to encode data for interchange.
While Twisted supports a basic netstring receiver protocol, it does not have a simple way to apply that to a non-network situation.

.. py:class:: NetstringParser

    This class parses strings piece by piece, either collecting the accumulated strings or invoking a callback for each one.

    .. py:method:: feed(data)

        :param data: a portion of netstring-formatted data
        :raises: :py:exc:`twisted.protocols.basic.NetstringParseError`

        Add arbitrarily-sized ``data`` to the incoming-data buffer.
        Any complete netstrings will trigger a call to the :py:meth:`stringReceived` method.

        Note that this method (like the Twisted class it is based on) cannot detect a trailing partial netstring at EOF - the data will be silently ignored.

    .. py:method:: stringReceived(string):

        :param string: the decoded string

        This method is called for each decoded string as soon as it is read completely.
        The default implementation appends the string to the :py:attr:`strings` attribute, but subclasses can do anything.

    .. py:attribute:: strings

        The strings decoded so far, if :py:meth:`stringReceived` is not overridden.

:py:mod:`buildbot.util.sautils`
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. py:module:: buildbot.util.sautils

This module contains a few utilities that are not included with SQLAlchemy.

.. py:class:: InsertFromSelect(table, select)

    :param table: table into which insert should be performed
    :param select: select query from which data should be drawn

    This class is taken directly from SQLAlchemy's `compiler.html <http://www.sqlalchemy.org/docs/core/compiler.html#compiling-sub-elements-of-a-custom-expression-construct>`_, and allows a Pythonic representation of ``INSERT INTO .. SELECT ..`` queries.

.. py:function:: sa_version()

    Return a 3-tuple representing the SQLAlchemy version.
    Note that older versions that did not have a ``__version__`` attribute are represented by ``(0,0,0)``.

:py:mod:`buildbot.util.pathmatch`
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. py:module:: buildbot.util.pathmatch

.. py:class:: Matcher

    This class implements the path-matching algorithm used by the data API.

    Patterns are tuples of strings, with strings beginning with a colon (``:``) denoting variables.
    A character can precede the colon to indicate the variable type:

    * ``i`` specifies an identifier (:ref:`identifier <type-identifier>`).
    * ``n`` specifies a number (parseable by ``int``).

    A tuple of strings matches a pattern if the lengths are identical, every variable matches and has the correct type, and every non-variable pattern element matches exactly.

    A matcher object takes patterns using dictionary-assignment syntax:

    .. code-block:: python

        ep = ChangeEndpoint()
        matcher[('change', 'n:changeid')] = ep

    and performs matching using the dictionary-lookup syntax:

    .. code-block:: python

        changeEndpoint, kwargs = matcher[('change', '13')]
        # -> (ep, {'changeid': 13})

    where the result is a tuple of the original assigned object (the ``Change`` instance in this case) and the values of any variables in the path.

    .. py:method:: iterPatterns()

        Returns an iterator which yields all patterns in the matcher as tuples of (pattern, endpoint).

:py:mod:`buildbot.util.topicmatch`
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. py:module:: buildbot.util.topicmatch

.. py:class:: TopicMatcher(topics)

    :param list topics: topics to match

    This class implements the AMQP-defined syntax: routing keys are treated as dot-separated sequences of words and matched against topics.
    A star (``*``) in the topic will match any single word, while an octothorpe (``#``) will match zero or more words.

    .. py:method:: matches(routingKey)

        :param string routingKey: routing key to examine
        :returns: True if the routing key matches a topic

:py:mod:`buildbot.util.subscription`
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The classes in the :py:mod:`buildbot.util.subscription` module are used for master-local subscriptions.
In the near future, all uses of this module will be replaced with message-queueing implementations that allow subscriptions and subscribers to span multiple masters.

:py:mod:`buildbot.util.croniter`
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This module is a copy of https://github.com/taichino/croniter, and provides support for converting cron-like time specifications into actual times.

:py:mod:`buildbot.util.state`
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

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

:py:mod:`buildbot.util.identifiers`
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. py:module:: buildbot.util.identifiers

This module makes it easy to manipulate identifiers.

.. py:function:: isIdentifier(maxLength, object)

    :param maxLength: maximum length of the identifier
    :param object: object to test for identifier-ness
    :returns: boolean

    Is object a :ref:`identifier <type-identifier>`?

.. py:function:: forceIdentifier(maxLength, str)

    :param maxLength: maximum length of the identifier
    :param str: string to coerce to an identifier
    :returns: identifier of maximum length ``maxLength``

    Coerce a string (assuming UTF-8 for bytestrings) into an identifier.
    This method will replace any invalid characters with ``_`` and truncate to the given length.

.. py:function:: incrementIdentifier(maxLength, str)

    :param maxLength: maximum length of the identifier
    :param str: identifier to increment
    :returns: identifier of maximum length ``maxLength``
    :raises: ValueError if no suitable identifier can be constructed

    "Increment" an identifier by adding a numeric suffix, while keeping the total length limited.
    This is useful when selecting a unique identifier for an object.
    Maximum-length identifiers like ``_999999`` cannot be incremented and will raise :py:exc:`ValueError`.

:py:mod:`buildbot.util.lineboundaries`
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. py:module:: buildbot.util.lineboundaries

.. py:class:: LineBoundaryFinder

    This class accepts a sequence of arbitrary strings and invokes a callback only with complete (newline-terminated) substrings.
    It buffers any partial lines until a subsequent newline is seen.
    It considers any of ``\r``, ``\n``, and ``\r\n`` to be newlines.
    Because of the ambiguity of an append operation ending in the character ``\r`` (it may be a bare ``\r`` or half of ``\r\n``), the last line of such an append operation will be buffered until the next append or flush.

    :param callback: asynchronous function to call with newline-terminated strings

    .. py:method:: append(text)

        :param text: text to append to the boundary finder
        :returns: Deferred

        Add additional text to the boundary finder.
        If the addition of this text completes at least one line, the callback will be invoked with as many complete lines as possible.

    .. py:method:: flush()

        :returns: Deferred

        Flush any remaining partial line by adding a newline and invoking the callback.

:py:mod:`buildbot.util.service`
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. py:module:: buildbot.util.service

This module implements some useful subclasses of Twisted services.

The first two classes are more robust implementations of two Twisted classes, and should be used universally in Buildbot code.

.. class:: AsyncMultiService

    This class is similar to :py:class:`twisted.application.service.MultiService`, except that it handles Deferreds returned from child services ``startService`` and ``stopService`` methods.

    Twisted's service implementation does not support asynchronous ``startService`` methods.
    The reasoning is that all services should start at process startup, with no need to coordinate between them.
    For Buildbot, this is not sufficient.
    The framework needs to know when startup has completed, so it can begin scheduling builds.
    This class implements the desired functionality, with a parent service's ``startService`` returning a Deferred which will only fire when all child services ``startService`` methods have completed.

    This class also fixes a bug with Twisted's implementation of ``stopService`` which ignores failures in the ``stopService`` process.
    With :py:class:`AsyncMultiService`, any errors in a child's ``stopService`` will be propagated to the parent's ``stopService`` method.

.. py:class:: AsyncService

    This class is similar to :py:class:`twisted.application.service.Service`, except that its ``setServiceParent`` method will return a Deferred.
    That Deferred will fire after the ``startService`` method has completed, if the service was started because the new parent was already running.

.. index:: Service utilities; ClusteredService

Some services in buildbot must have only one "active" instance at any given time.
In a single-master configuration, this requirement is trivial to maintain.
In a multiple-master configuration, some arbitration is required to ensure that the service is always active on exactly one master in the cluster.

For example, a particular daily scheduler could be configured on multiple masters, but only one of them should actually trigger the required builds.

.. py:class:: ClusteredService

    A base class for a service that must have only one "active" instance in a buildbot configuration.

    Each instance of the service is started and stopped via the usual twisted ``startService`` and ``stopService`` methods.
    This utility class hooks into those methods in order to run an arbitration strategy to pick the one instance that should actually be "active".

    The arbitration strategy is implemented via a polling loop.
    When each service instance starts, it immediately offers to take over as the active instance (via ``_claimService``).

    If successful, the ``activate`` method is called.
    Once active, the instance remains active until it is explicitly stopped (eg, via ``stopService``) or otherwise fails.
    When this happens, the ``deactivate`` method is invoked and the "active" status is given back to the cluster (via ``_unclaimService``).

    If another instance is already active, this offer fails, and the instance will poll periodically to try again.
    The polling strategy helps guard against active instances that might silently disappear and leave the service without any active instance running.

    Subclasses should use these methods to hook into this activation scheme:

    .. method:: activate()

        When a particular instance of the service is chosen to be the one "active" instance, this method is invoked.
        It is the corollary to twisted's ``startService``.

    .. method:: deactivate()

        When the one "active" instance must be deactivated, this method is invoked.
        It is the corollary to twisted's ``stopService``.

    .. method:: isActive()

        Returns whether this particular instance is the active one.

    The arbitration strategy is implemented via the following required methods:

    .. method:: _getServiceId()

        The "service id" uniquely represents this service in the cluster.
        Each instance of this service must have this same id, which will be used in the arbitration to identify candidates for activation.
        This method may return a Deferred.

    .. method:: _claimService()

        An instance is attempting to become the one active instance in the cluster.
        This method must return `True` or `False` (optionally via a Deferred) to represent whether this instance's offer to be the active one was accepted.
        If this returns `True`, the ``activate`` method will be called for this instance.

    .. method:: _unclaimService()

        Surrender the "active" status back to the cluster and make it available for another instance.
        This will only be called on an instance that successfully claimed the service and has been activated and after its ``deactivate`` has been called.
        Therefore, in this method it is safe to reassign the "active" status to another instance.
        This method may return a Deferred.

.. py:class:: SharedService

    This class implements a generic Service that needs to be instantiated only once according to its parameters.
    It is a common use case to need this for accessing remote services.
    Having a shared service allows to limit the number of simultaneous access to the same remote service.
    Thus, several completely independent Buildbot services can use that :py:class:`SharedService` to access the remote service, and automatically synchronize themselves to not overwhelm it.

    .. py:method:: __init__(self, *args, **kwargs)

        Constructor of the service.

        Note that unlike :py:class:`BuildbotService`, :py:class:`SharedService` is not reconfigurable and uses the classical constructor method.

        Reconfigurability would mean to add some kind of reference counting of the users, which will make the design much more complicated to use.
        This means that the SharedService will not be destroyed when there is no more users, it will be destroyed at the master's stopService
        It is important that those :py:class:`SharedService` life cycles are properly handled.
        Twisted will indeed wait for any thread pool to finish at master stop, which will not happen if the thread pools are not properly closed.

        The lifecycle of the SharedService is the same as a service, it must implement startService and stopService in order to allocate and free its resources.

    .. py:method:: getName(cls, *args, **kwargs)

        Class method.
        Takes same arguments as the constructor of the service.
        Get a unique name for that instance of a service.
        This returned name is the key inside the parent's service dictionary that is used to decide if the instance has already been created before or if there is a need to create a new object.
        Default implementation will hash args and kwargs and use ``<classname>_<hash>`` as the name.

    .. py:method:: getService(cls, parentService, *args, **kwargs)

        :param parentService: an :py:class:`AsyncMultiService` where to lookup and register the :py:class:`SharedService` (usually the root service, the master)
        :returns: instance of the service via Deferred

        Class method.
        Takes same arguments as the constructor of the service (plus the `parentService` at the beginning of the list).
        Construct an instance of the service if needed, and place it at the beginning of the `parentService` service list.
        Placing it at the beginning will guarantee that the :py:class:`SharedService` will be stopped after the other services.

.. py:class:: BuildbotService

    This class is the combinations of all `Service` classes implemented in buildbot.
    It is Async, MultiService, and Reconfigurable, and designed to be eventually the base class for all buildbot services.
    This class makes it easy to manage (re)configured services.

    The design separates the check of the config and the actual configuration/start.
    A service sibling is a configured object that has the same name of a previously started service.
    The sibling configuration will be used to configure the running service.

    Service lifecycle is as follow:

    * Buildbot master start

    * Buildbot is evaluating the configuration file.
      BuildbotServices are created, and checkConfig() are called by the generic constructor.

    * If everything is fine, all services are started.
      BuildbotServices startService() is called, and call reconfigService() for the first time.

    * User reconfigures buildbot.

    * Buildbot is evaluating the configuration file.
      BuildbotServices siblings are created, and checkConfig() are called by the generic constructor.

    * BuildbotServiceManager is figuring out added services, removed services, unchanged services

    * BuildbotServiceManager calls stopService() for services that disappeared from the configuration.

    * BuildbotServiceManager calls startService() like in buildbot start phase for services that appeared from the configuration.

    * BuildbotServiceManager calls reconfigService() for the second time for services that have their configuration changed.


    .. py:method:: __init__(self, *args, **kwargs)

        Constructor of the service.
        The constructor initializes the service, calls checkConfig() and stores the config arguments in private attributes.

        This should *not* be overridden by subclasses, as they should rather override checkConfig.

    .. py:method:: checkConfig(self, *args, **kwargs)

        Please override this method to check the parameters of your config.
        Please use :py:func:`buildbot.config.error` for error reporting.
        You can replace them ``*args, **kwargs`` by actual constructor like arguments with default args, and it have to match self.reconfigService
        This method is synchronous, and executed in the context of the master.cfg.
        Please don't block, or use deferreds in this method.
        Remember that the object that runs checkConfig is not always the object that is actually started.
        The checked configuration can be passed to another sibling service.
        Any actual resource creation shall be handled in reconfigService() or startService()

    .. py:method:: reconfigService(self, *args, **kwargs)

        This method is called at buildbot startup, and buildbot reconfig.
        `*args` and `**kwargs` are the configuration arguments passed to the constructor in master.cfg.
        You can replace ``them *args, **kwargs`` by actual constructor like arguments with default args, and it have to match self.checkConfig

        Returns a deferred that should fire when the service is ready.
        Builds are not started until all services are configured.

        BuildbotServices must be aware that during reconfiguration, their methods can still be called by running builds.
        So they should atomically switch old configuration and new configuration, so that the service is always available.

        If this method raises :py:class:`NotImplementedError`, it means the service is legacy, and do not support reconfiguration.
        The :py:class:`BuildbotServiceManager` parent, will detect this, and swap old service with new service.
        This behaviour allow smooth transition of old code to new reconfigurable service lifecycle but shall not be used for new code.

    .. py:method:: reconfigServiceWithSibling(self, sibling)

        Internal method that finds the configuration bits in a sibling, an object with same class that is supposed to replace it from a new configuration.
        We want to reuse the service started at master startup and just reconfigure it.
        This method handles necessary steps to detect if the config has changed, and eventually call self.reconfigService()

    .. py:method:: renderSecrets(self, *args)

        Utility method which renders a list of parameters which can be interpolated as a secret.
        This is meant for services which have their secrets parameter configurable as positional arguments.
        If there are several argument, the secrets are interpolated in parallel, and a list of result is returned via deferred.
        If there is one argument, the result is directly returned.

        .. note::

            For keyword arguments, a simpler method is to use the ``secrets`` class variable, which items
            will be automatically interpolated just before reconfiguration.

        .. code-block:: python

                def reconfigService(self, user, password, ...)
                    user, password = yield self.renderSecrets(user, password)

        .. code-block:: python

                def reconfigService(self, token, ...)
                    token = yield self.renderSecrets(token)

        .. code-block:: python

                secrets = ("user", "password")
                def reconfigService(self, user=None, password=None, ...):
                    # nothing to do user and password will be automatically interpolated


    Advanced users can derive this class to make their own services that run inside buildbot, and follow the application lifecycle of buildbot master.

    Such services are singletons accessible in nearly every objects of buildbot (buildsteps, status, changesources, etc) using self.master.namedServices['<nameOfYourService'].

    As such, they can be used to factorize access to external services, available e.g using a REST api.
    Having a single service will help with caching, and rate-limiting access of those APIs.

    Here is an example on how you would integrate and configure a simple service in your `master.cfg`:

    .. code-block:: python

        class MyShellCommand(ShellCommand):

            def getResultSummary(self):
                # access the service attribute
                service = self.master.namedServices['myService']
                return dict(step=u"arg value: %d" % (service.arg1,))

        class MyService(BuildbotService):
            name = "myService"

            def checkConfig(self, arg1):
                if not isinstance(arg1, int):
                    config.error("arg1 must be an integer while it is %r" % (arg1,))
                    return
                if arg1 < 0:
                    config.error("arg1 must be positive while it is %d" % (arg1,))

            def reconfigService(self, arg1):
                self.arg1 = arg1
                return defer.succeed(None)

        c['schedulers'] = [
            ForceScheduler(
                name="force",
                builderNames=["testy"])]

        f = BuildFactory()
        f.addStep(MyShellCommand(command='echo hei'))
        c['builders'] = [
            BuilderConfig(name="testy",
                          workernames=["local1"],
                          factory=f)]

        c['services'] = [
            MyService(arg1=1)
        ]

:py:mod:`buildbot.util.httpclientservice`
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. py:class:: HTTPClientService

    This class implements a SharedService for doing http client access.
    The module automatically chooses from `txrequests`_ and `treq`_ and uses whichever is installed.
    It provides minimalistic API similar to the one from `txrequests`_ and `treq`_.
    Having a SharedService for this allows to limits the number of simultaneous connection for the same host.
    While twisted application can managed thousands of connections at the same time, this is often not the case for the services buildbot controls.
    Both `txrequests`_ and `treq`_ use keep-alive connection polling.
    Lots of HTTP REST API will however force a connection close in the end of a transaction.

    .. note::

        The API described here is voluntary minimalistic, and reflects what is tested.
        As most of this module is implemented as a pass-through to the underlying libraries, other options can work but have not been tested to work in both backends.
        If there is a need for more functionality, please add new tests before using them.

    .. py:staticmethod:: getService(master, base_url, auth=None, headers=None, debug=None, verify=None)

        :param master: the instance of the master service (available in self.master for all the :py:class:`BuildbotService` instances)
        :param base_url: The base http url of the service to access. e.g. ``http://github.com/``
        :param auth: Authentication information. If auth is a tuple then ``BasicAuth`` will be used. e.g ``('user', 'passwd')``
            It can also be a :mod:`requests.auth` authentication plugin.
            In this case `txrequests`_ will be forced, and `treq`_ cannot be used.
        :param headers: The headers to pass to every requests for this url
        :param debug: log every requests and every response.
        :param verify: disable the SSL verification.

        :returns: instance of :`HTTPClientService`

        Get an instance of the SharedService.
        There is one instance per base_url and auth.

        The constructor initialize the service, and store the config arguments in private attributes.

        This should *not* be overridden by subclasses, as they should rather override checkConfig.


    .. py:method:: get(endpoint, params=None)

        :param endpoint: endpoint relative to the base_url (starts with ``/``)
        :param params: optional dictionary that will be encoded in the query part of the url (e.g. ``?param1=foo``)
        :returns: implementation of :`IHTTPResponse` via deferred

        Performs a HTTP ``GET``

    .. py:method:: delete(endpoint, params=None)

        :param endpoint: endpoint relative to the base_url (starts with ``/``)
        :param params: optional dictionary that will be encoded in the query part of the url (e.g. ``?param1=foo``)
        :returns: implementation of :`IHTTPResponse` via deferred

        Performs a HTTP ``DELETE``

    .. py:method:: post(endpoint, data=None, json=None, params=None)

        :param endpoint: endpoint relative to the base_url (starts with ``/``)
        :param data: optional dictionary that will be encoded in the body of the http requests as ``application/x-www-form-urlencoded``
        :param json: optional dictionary that will be encoded in the body of the http requests as ``application/json``
        :param params: optional dictionary that will be encoded in the query part of the url (e.g. ``?param1=foo``)
        :returns: implementation of :`IHTTPResponse` via deferred

        Performs a HTTP ``POST``

        .. note::

            json and data cannot be used at the same time.

    .. py:method:: put(endpoint, data=None, json=None, params=None)

        :param endpoint: endpoint relative to the base_url (starts with ``/``)
        :param data: optional dictionary that will be encoded in the body of the http requests as ``application/x-www-form-urlencoded``
        :param json: optional dictionary that will be encoded in the body of the http requests as ``application/json``
        :param params: optional dictionary that will be encoded in the query part of the url (e.g. ``?param1=foo``)
        :returns: implementation of :`IHTTPResponse` via deferred

        Performs a HTTP ``PUT``

        .. note::

            json and data cannot be used at the same time.

.. py:class:: IHTTPResponse

    .. note::

        :class:`IHTTPResponse` is a subset of `treq`_ :py:class:`Response` API described `here <https://treq.readthedocs.io/en/latest/api.html#module-treq.response>`_
        The API it is voluntarily minimalistic and reflects what is tested and reliable to use with the three backends (including fake).
        The api is a subset of the `treq`_ API, which is itself a superset of `twisted IResponse API`_.
        `treq`_ is thus implemented as passthrough.

        Notably:

        * There is no api to automatically decode content, as this is not implemented the same in both backends.
        * There is no api to stream content as the two libraries have very different way for doing it, and we do not see use-case where buildbot would need to transfer large content to the master.

    .. py:method:: content()

        :returns: raw (``bytes``) content of the response via deferred

    .. py:method:: json()

        :returns: json decoded content of the response via deferred

    .. py:attribute:: code

        :returns: http status code of the request's response (e.g 200)

.. _txrequests: https://pypi.python.org/pypi/txrequests
.. _treq: https://pypi.python.org/pypi/treq
.. _twisted IResponse API: https://twistedmatrix.com/documents/current/api/twisted.web.iweb.IResponse.html

:py:mod:`buildbot.test.fake.httpclientservice`
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. py:class:: HTTPClientService

    This class implements a fake version of the :class:`buildbot.util.httpclientservice.HTTPClientService` that needs to be used for testing services which needs http client access.
    It implements the same APIs as :class:`buildbot.util.httpclientservice.HTTPClientService`, plus one that should be used to register the expectations.
    It should be registered by the test case before the tested service actually requests an HTTPClientService instance, with the same parameters.
    It will then replace the original implementation automatically (no need to patch anything).
    The testing methodology is based on `AngularJS ngMock`_.

    .. py:method:: getFakeService(cls, master, case, *args, **kwargs):

        :param master: the instance of a fake master service
        :param case: a :py:class:`twisted.python.unittest.TestCase` instance

        :py:meth:`getFakeService` returns a fake :py:class:`HTTPClientService`, and should be used in place of :py:meth:`getService`.

        on top of :py:meth:`getService` it will make sure the original :py:class:`HTTPClientService` is not called, and assert that all expected http requests have been described in the test case.


    .. py:method:: expect(self, method, ep, params=None, data=None, json=None, code=200,
                          content=None, content_json=None):

        :param method: expected HTTP method
        :param ep: expected endpoint
        :param params: optional expected query parameters
        :param data: optional expected non-json data (bytes)
        :param json: optional expected json data (dictionary or list or string)
        :param code: optional http code that will be received
        :param content: optional content that will be received
        :param content_json: optional content encoded in json that will be received

        Records an expectation of HTTP requests that will happen during the test.
        The order of the requests is important.
        All the request expectation must be defined in the test.

        example:

        .. code-block:: python

            from twisted.internet import defer
            from twisted.trial import unittest

            from buildbot.test.fake import httpclientservice as fakehttpclientservice
            from buildbot.util import httpclientservice
            from buildbot.util import service


            class myTestedService(service.BuildbotService):
                name = 'myTestedService'

                @defer.inlineCallbacks
                def reconfigService(self, baseurl):
                    self._http = yield httpclientservice.HTTPClientService.getService(self.master, baseurl)

                @defer.inlineCallbacks
                def doGetRoot(self):
                    res = yield self._http.get("/")
                    # note that at this point, only the http response headers are received
                    if res.code != 200:
                        raise Exception("%d: server did not succeed" % (res.code))
                    res_json = yield res.json()
                    # res.json() returns a deferred to account for the time needed to fetch the entire body
                    return res_json


            class Test(unittest.SynchronousTestCase):

                def setUp(self):
                    baseurl = 'http://127.0.0.1:8080'
                    self.parent = service.MasterService()
                    self._http = self.successResultOf(fakehttpclientservice.HTTPClientService.getFakeService(
                        self.parent, self, baseurl))
                    self.tested = myTestedService(baseurl)

                    self.successResultOf(self.tested.setServiceParent(self.parent))
                    self.successResultOf(self.parent.startService())

                def test_root(self):
                    self._http.expect("get", "/", content_json={'foo': 'bar'})

                    response = self.successResultOf(self.tested.doGetRoot())
                    self.assertEqual(response, {'foo': 'bar'})

                def test_root_error(self):
                    self._http.expect("get", "/", content_json={'foo': 'bar'}, code=404)

                    response = self.failureResultOf(self.tested.doGetRoot())
                    self.assertEqual(response.getErrorMessage(), '404: server did not succeed')

.. _AngularJS ngMock: https://docs.angularjs.org/api/ngMock/service/$httpBackend

:py:mod:`buildbot.util.ssl`
~~~~~~~~~~~~~~~~~~~~~~~~~~~

This module is a copy of :py:mod:`twisted.internet.ssl` except it won't crash with :py:class:`ImportError` if :py:mod:`pyopenssl` is not installed.
If you need to use :py:mod:`twisted.internet.ssl`, please instead use :py:mod:`buildbot.util.ssl`, and call :py:func:`ssl.ensureHasSSL` in :py:meth:`checkConfig` to provide helpful message to the user, only if he enabled SSL for your plugin.

.. py:function:: ensureHasSSL(plugin_name)

    :param plugin_name: name of the plugin. Usually ``self.__class__.__name__``

    Call this function to provide helpful config error to the user in case of ``OpenSSL`` not installed.


.. py:function:: skipUnless(f)

    :param f: decorated test

    Test decorator which will skip the test if ``OpenSSL`` is not installed.
