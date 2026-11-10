Buildbot Coding Style
=====================

Documentation
-------------

Buildbot strongly encourages developers to document the methods, behavior, and usage of classes
that users might interact with. However, this documentation should be in ``.rst`` files under
``master/docs/developer``, rather than in docstrings within the code. For private methods or where
code deserves some kind of explanatory preface, use comments instead of a docstring. While some
docstrings remain within the code, these should be migrated to documentation files and removed as
the code is modified.

Within the reStructuredText files, write each English sentence on its own line. While this does not
affect the generated output, it makes git diffs between versions of the documentation easier to
read, as they are not obscured by changes due to re-wrapping. This convention is not followed
everywhere, but we are slowly migrating documentation from the old (wrapped) style as we update it.

Symbol Names
------------

Buildbot follows `PEP8 <https://www.python.org/dev/peps/pep-0008/>`_ regarding the formatting of symbol names.

Due to historical reasons, most of the public API uses interCaps naming style To preserve backwards
compatibility, the public API should continue using interCaps naming style. That is, you should
spell public API methods and functions with the first character in lower-case, and the first letter
of subsequent words capitalized, e.g., ``compareToOther`` or ``getChangesGreaterThan``. The public
API refers to the documented API that external developers can rely on. See section on the
definition of the public API in :ref:`Public-API`.

Everything else should use the style recommended by PEP8.

In summary:

=========================================== ============
Symbol Type                                 Format
=========================================== ============
Methods and functions                       under_scores
Method and function arguments               under_scores
Public API methods and functions            interCaps
Public API method and function arguments    interCaps
Classes                                     InitialCaps
Variables                                   under_scores
Constants                                   ALL_CAPS
=========================================== ============

Twisted Idioms
--------------

Programming with Twisted Python can be daunting.  But sticking to a few
well-defined patterns can help avoid surprises.

Prefer Asynchronous Methods
~~~~~~~~~~~~~~~~~~~~~~~~~~~

If you're writing a method that doesn't currently block, but could conceivably
block sometime in the future, make it a coroutine (``async def``) and document that it is asynchronous.
Just about anything might block - even getters and setters!

Older code returns a Deferred instead; see :ref:`Style-Coroutines` for how the two interoperate.

Helpful Twisted Classes
~~~~~~~~~~~~~~~~~~~~~~~

Twisted has some useful, but little-known classes.
Brief descriptions follow, but you should consult the API documentation or source code
for the full details.

:class:`twisted.internet.task.LoopingCall`
    Calls an asynchronous function repeatedly at set intervals.
    Note that this will stop looping if the function fails.
    In general, you will want to wrap the function to capture and log errors.

:class:`twisted.application.internet.TimerService`
    Similar to ``t.i.t.LoopingCall``, but implemented as a service that will automatically start
    and stop the function calls when the service starts and stops.
    See the warning about failing functions for ``t.i.t.LoopingCall``.

Sequences of Operations
~~~~~~~~~~~~~~~~~~~~~~~

Especially in Buildbot, we're often faced with executing a sequence of
operations, many of which may block.

In all cases where this occurs, there is a danger of pre-emption, so exercise
the same caution you would if writing a threaded application.

For simple cases, you can use nested callback functions. For anything more complex, and in all new
code, use coroutines (``async def``). In all cases, please prefer maintainability and readability over performance.

Nested Callbacks
................

First, an admonition: do not create extra class methods that represent the continuations of the first:


.. code-block:: python

    def myMethod(self):
        d = ...
        d.addCallback(self._myMethod_2) # BAD!
    def _myMethod_2(self, res):         # BAD!
        ...

Invariably, this extra method gets separated from its parent as the code
evolves, and the result is completely unreadable. Instead, include all of the
code for a particular function or method within the same indented block, using
nested functions:

.. code-block:: python

    def getRevInfo(revname):
        # for demonstration only! see below for a better implementation with inlineCallbacks
        results = {}
        d = defer.succeed(None)
        def rev_parse(_): # note use of '_' to quietly indicate an ignored parameter
            return utils.getProcessOutput(git, [ 'rev-parse', revname ])
        d.addCallback(rev_parse)
        def parse_rev_parse(res):
            results['rev'] = res.strip()
            return utils.getProcessOutput(git, [ 'log', '-1', '--format=%s%n%b', results['rev'] ])
        d.addCallback(parse_rev_parse)
        def parse_log(res):
            results['comments'] = res.strip()
        d.addCallback(parse_log)
        def set_results(_):
            return results
        d.addCallback(set_results)
        return d

It is usually best to make the first operation occur within a callback, as the deferred machinery
will then handle any exceptions as a failure in the outer Deferred. As a shortcut,
``d.addCallback`` can work as a decorator:

.. code-block:: python

    d = defer.succeed(None)
    @d.addCallback
    def rev_parse(_): # note use of '_' to quietly indicate an ignored parameter
        return utils.getProcessOutput(git, [ 'rev-parse', revname ])

.. note::

    ``d.addCallback`` is not really a decorator as it does not return a modified function. As a
    result, in the previous code, ``rev_parse`` value is actually the Deferred. In general, the
    coroutines (``async def``) are preferred inside new code as they keep the code easier to
    read. As a general rule of thumb, when you need more than 2 callbacks in the same method, it's
    time to switch to a coroutine. This would be for example the case for the
    :py:func:`getRevInfo` example. See this `discussion <:pull:`2523`>`_ with Twisted experts for
    more information.

Be careful with local variables. For example, if ``parse_rev_parse``, above,
merely assigned ``rev = res.strip()``, then that variable would be local to
``parse_rev_parse`` and not available in ``set_results``. Mutable variables
(dicts and lists) at the outer function level are appropriate for this purpose.

.. note:: Do not try to build a loop in this style by chaining multiple
    Deferreds!  Unbounded chaining can result in stack overflows, at least on older
    versions of Twisted. Use a coroutine instead.

In most of the cases, if you need more than two callbacks in a method, it is more readable and
maintainable to use a coroutine.

.. _Style-Coroutines:

Coroutines
..........

New code is written as coroutines, with ``async def`` and ``await``.
They allow you to use all of the usual Pythonic control structures in their natural form.
In particular, it is easy to represent a loop or even nested loops in this style without losing any readability.

.. code-block:: python

    async def mymethod(self, x, y):
        xval = await getSomething(x)

        for z in await getZValues():
            y += z

        if xval > 10:
            return xval + y

        self.someOtherMethod()

A coroutine can ``await`` a Deferred directly.
The other way round, Twisted and most of Buildbot expect a Deferred, not a coroutine, from the
functions they call.
When a coroutine is called from such a place (an overridden method, a callback, a service's
``startService``...), convert it:

* decorate the method with :py:func:`buildbot.util.twisted.async_to_deferred`, so that calling it
  returns a Deferred;
* or wrap a single call with ``defer.Deferred.fromCoroutine(coro())``.

The previous :py:func:`getRevInfo` example implementation should rather be written as:

.. code-block:: python

    async def getRevInfo(revname):
        results = {}
        res = await utils.getProcessOutput(git, [ 'rev-parse', revname ])
        results['rev'] = res.strip()
        res = await utils.getProcessOutput(git, [ 'log', '-1', '--format=%s%n%b',
                                                 results['rev'] ])
        results['comments'] = res.strip()
        return results

Always import ``defer`` as a module, not the names within it.

inlineCallbacks
...............

Much of the existing code uses :class:`twisted.internet.defer.inlineCallbacks`, the generator-based
predecessor of coroutines (``yield`` instead of ``await``).
Do not use it in new code.

Note that code using ``deferredGenerator`` is no longer acceptable in Buildbot.

Locking
.......

Remember that asynchronous programming does not free you from the need to worry about concurrency
issues. In particular, if you are executing a sequence of operations, and each time you wait for a
Deferred, other arbitrary actions can take place.

In general, you should try to perform actions atomically, but for the rare situations that require
synchronization, the following might be useful:

* :py:class:`twisted.internet.defer.DeferredLock`
* :py:func:`buildbot.util.misc.deferredLocked`

Joining Sequences
~~~~~~~~~~~~~~~~~

It's often the case that you want to perform multiple operations in parallel and rejoin the results at the end.
For this purpose, you may use a `DeferredList <http://twistedmatrix.com/documents/current/api/twisted.internet.defer.DeferredList.html>`_:

.. code-block:: python

    def getRevInfo(revname):
        results = {}
        finished = dict(rev_parse=False, log=False)

        rev_parse_d = utils.getProcessOutput(git, [ 'rev-parse', revname ])
        def parse_rev_parse(res):
            return res.strip()
        rev_parse_d.addCallback(parse_rev_parse)

        log_d = utils.getProcessOutput(git, [ 'log', '-1', '--format=%s%n%b', results['rev'] ])
        def parse_log(res):
            return res.strip()
        log_d.addCallback(parse_log)

        d = defer.DeferredList([rev_parse_d, log_d], consumeErrors=1, fireOnFirstErrback=1)
        def handle_results(results):
            return dict(rev=results[0][1], log=results[1][1])
        d.addCallback(handle_results)
        return d

Here, the deferred list will wait for both ``rev_parse_d`` and ``log_d`` to fire, or for one of
them to fail. You may attach callbacks and errbacks to a ``DeferredList`` just as you would with a
deferred.

Logging
~~~~~~~

New code logs through the :py:mod:`twisted.logger` API, with one logger per module, not through the
legacy ``twisted.python.log.msg`` and ``log.err``:

.. code-block:: python

    from twisted.logger import Logger

    log = Logger()

    def process(self, name):
        log.info("processing {name}", name=name)
        try:
            ...
        except Exception:
            log.failure("failed to process {name}", name=name)

Pass values as keyword arguments referenced in the format string, rather than pre-formatting the
message (no f-strings or ``%``): the message is only rendered when needed and the values stay
available to observers.
Use ``log.failure`` inside an ``except`` block to log the current exception with its traceback.

Functions running outside of the main thread
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

It is very important in Twisted to be able to distinguish functions that runs in the main thread
and functions that don't, as reactors and deferreds can only be used in the main thread. To make
this distinction clearer, every function meant to be run in a secondary thread must be prefixed
with ``thd_``.
