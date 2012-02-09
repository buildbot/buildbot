Buildbot Coding Style
=====================

Symbol Names
------------

Buildbot follows `PEP8 <http://www.python.org/dev/peps/pep-0008/>` regarding
the formatting of symbol names.

The single exception in naming of functions and methods. Because Buildbot uses
Twisted so heavily, and Twisted uses interCaps, Buildbot methods should do the
same. That is, methods and functions should be spelled with the first character
in lower-case, and the first letter of subsequent words capitalized, e.g.,
``compareToOther`` or ``getChangesGreaterThan``. This point is not applied very
consistently in Buildbot, but let's try to be consistent in new code. 

Twisted Idioms
--------------

Programming with Twisted Python can be daunting.  But sticking to a few
well-defined patterns can help avoid surprises.

Prefer to Return Deferreds
~~~~~~~~~~~~~~~~~~~~~~~~~~

If you're writing a method that doesn't currently block, but could conceivably
block sometime in the future, return a Deferred and document that it does so.
Just about anything might block - even getters and setters!

Helpful Twisted Classes
~~~~~~~~~~~~~~~~~~~~~~~

Twisted has some useful, but little-known classes.  They are listed here with
brief descriptions, but you should consult the API documentation or source code
for the full details.

:class:`twisted.internet.task.LoopingCall`
    Calls an asynchronous function repeatedly at set intervals.

:class:`twisted.application.internet.TimerService`
    Similar to ``t.i.t.LoopingCall``, but implemented as a service that will
    automatically start and stop the function calls when the service is started and
    stopped.

Sequences of Operations
~~~~~~~~~~~~~~~~~~~~~~~

Especially in Buildbot, we're often faced with executing a sequence of
operations, many of which may block.

In all cases where this occurs, there is a danger of pre-emption, so exercise
the same caution you would if writing a threaded application.

For simple cases, you can use nested callback functions. For more complex cases, deferredGenerator is appropriate.

Nested Callbacks
................

First, an admonition: do not create extra class methods that represent the continuations of the first::

    def myMethod(self):
        d = ...
        d.addCallback(self._myMethod_2) # BAD!
    def _myMethod_2(self, res):         # BAD!
        # ...

Invariably, this extra method gets separated from its parent as the code
evolves, and the result is completely unreadable. Instead, include all of the
code for a particular function or method within the same indented block, using
nested functions::

    def getRevInfo(revname):
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

it is usually best to make the first operation occur within a callback, as the
deferred machinery will then handle any exceptions as a failure in the outer
Deferred.  As a shortcut, ``d.addCallback`` works as a decorator::

    d = defer.succeed(None)
    @d.addCallback
    def rev_parse(_): # note use of '_' to quietly indicate an ignored parameter
        return utils.getProcessOutput(git, [ 'rev-parse', revname ])

Be careful with local variables. For example, if ``parse_rev_parse``, above,
merely assigned ``rev = res.strip()``, then that variable would be local to
``parse_rev_parse`` and not available in ``set_results``. Mutable variables
(dicts and lists) at the outer function level are appropriate for this purpose.

.. note:: do not try to build a loop in this style by chaining multiple
    Deferreds!  Unbounded chaining can result in stack overflows, at least on older
    versions of Twisted. Use ``deferredGenerator`` instead. 

deferredGenerator
.................

:class:`twisted.internet.defer.deferredGenerator` is a great help to writing
code that makes a lot of asynchronous calls.  Refer to the Twisted
documentation for the details, but the style within Buildbot is as follows::

    from twisted.internet import defer

    @defer.deferredGenerator
    def mymethod(self, x, y):
        wfd = defer.waitForDeferred(
                getSomething(x))
        yield wfd
        xval = wfd.getResult()

        yield xval + y # return value

The key points to notice here:

* Always import ``defer`` as a module, not the names within it.
* Use the decorator form of ``deferredGenerator``
* For each ``waitForDeferred`` call, use the variable ``wfd``, and assign to it
  on one line, with the operation returning the Deferred on the next.
* While ``wfd.getResult()`` can be used in an expression, if that expression is
  complex, pull it out into a simple assignment.  This helps reviewers scanning
  the code for missing ``getResult`` calls.
* When ``yield`` is used to return a value, add a comment to that effect, since
  this can often be missed.

The great advantage of ``deferredGenerator`` is that it allows you to use all
of the usual Pythonic control structures in their natural form. In particular,
it is easy to represent a loop, or even nested loops, in this style without
losing any readability. The downside, of course, is the rather verbose style
and the requirement that ``getResult`` be called even when no result is needed
- this is easy to forget!  Twisted's ``inlineCallbacks`` fixes many of these
shortcomings, but is not usable in Buildbot, because Buildbot is still
compatible with Python-2.4.  This will change after Buildbot-0.8.6
(:bb:bug:`2157`).

As a reminder, Python-2.4 also does not support try/finally blocks in
generators.

Joining Sequences
~~~~~~~~~~~~~~~~~

It's often the case that you'll want to perform multiple operations in
parallel, and re-join the results at the end. For this purpose, you'll want to
use a `DeferredList
<http://twistedmatrix.com/documents/current/api/twisted.internet.defer.DeferredList.html>`::

    def getRevInfo(revname):
        results = {}
        finished = dict(rev_parse=False, log=False)

        rev_parse_d = utils.getProcessOutput(git, [ 'rev-parse', revname ])
        def parse_rev_parse(res):
            return res.strip()
        rev_parse_d.addCallback(parse_rev_parse)

        log_d = utils.getProcessOutput(git, [ 'log', '-1', '--format=%s%n%b', results['rev'] ]))
        def parse_log(res):
            return res.strip()
        log_d.addCallback(parse_log)

        d = defer.DeferredList([rev_parse_d, log_d], consumeErrors=1, fireOnFirstErrback=1)
        def handle_results(results):
            return dict(rev=results[0][1], log=results[1][1])
        d.addCallback(handle_results)
        return d

Here the deferred list will wait for both ``rev_parse_d`` and ``log_d`` to
fire, or for one of them to fail.  Callbacks and errbacks can be attached to a
``DeferredList`` just as for a deferred.

Writing Buildbot Tests
----------------------

In general, we are trying to ensure that new tests are *good*.  So what makes
a good test?

.. _Tests-Independent-of-Time:

Independent of Time
~~~~~~~~~~~~~~~~~~~

Tests that depend on wall time will fail. As a bonus, they run very slowly. Do
not use :meth:`reactor.callLater` to wait "long enough" for something to happen.

For testing things that themselves depend on time, consider using
:class:`twisted.internet.tasks.Clock`.  This may mean passing a clock instance to
the code under test, and propagating that instance as necessary to ensure that
all of the code using :meth:`callLater` uses it.  Refactoring code for
testability is difficult, but wortwhile.

For testing things that do not depend on time, but for which you cannot detect
the "end" of an operation: add a way to detect the end of the operation!

Clean Code
~~~~~~~~~~

Make your tests readable. This is no place to skimp on comments! Others will
attempt to learn about the expected behavior of your class by reading the
tests. As a side note, if you use a :class:`Deferred` chain in your test, write
the callbacks as nested functions, rather than using object methods with funny
names::

    def testSomething(self):
        d = doThisFirst()
        def andThisNext(res):
            pass # ...
        d.addCallback(andThisNext)
        return d

This isolates the entire test into one indented block. It is OK to add methods
for common functionality, but give them real names and explain in detail what
they do.

Good Name
~~~~~~~~~

Your test module should be named after the package or class it tests, replacing
``.`` with ``_`` and omitting the ``buildbot_``. For example,
:file:`test_status_web_authz_Authz.py` tests the :class:`Authz` class in
:file:`buildbot/status/web/authz.py`. Modules with only one class, or a few
trivial classes, can be tested in a single test module. For more complex
situations, prefer to use multiple test modules.

Test method names should follow the pattern :samp:`test_{METHOD}_{CONDITION}`
where *METHOD* is the method being tested, and *CONDITION* is the
condition under which it's tested. Since we can't always test a single
method, this is not a hard-and-fast rule.

Assert Only One Thing
~~~~~~~~~~~~~~~~~~~~~

Each test should have a single assertion. This may require a little bit of work
to get several related pieces of information into a single Python object for
comparison. The problem with multiple assertions is that, if the first
assertion fails, the remainder are not tested.  The test results then do not
tell the entire story.

If you need to make two unrelated assertions, you should be running two tests.

Use Mocks and Stubs
~~~~~~~~~~~~~~~~~~~

Mocks assert that they are called correctly. Stubs provide a predictable base
on which to run the code under test. See
`Mock Object <http://en.wikipedia.org/wiki/Mock_object>`_ and
`Method Stub <http://en.wikipedia.org/wiki/Method_stub>`_.

Mock objects can be constructed easily using the aptly-named
`mock <http://www.voidspace.org.uk/python/mock/>`_ module, which is a
requirement for Buildbot's tests.

One of the difficulties with Buildbot is that interfaces are unstable and
poorly documented, which makes it difficult to design stubs.  A common
repository for stubs, however, will allow any interface changes to be reflected
in only one place in the test code.

Small Tests
~~~~~~~~~~~

The shorter each test is, the better. Test as little code as possible in each test.

It is fine, and in fact encouraged, to write the code under test in such a way
as to facilitate this. As an illustrative example, if you are testing a new
Step subclass, but your tests require instantiating a BuildMaster, you're
probably doing something wrong! (Note that this rule is almost universally
violated in the existing buildbot tests).

This also applies to test modules.  Several short, easily-digested test modules
are preferred over a 1000-line monster.

Isolation
~~~~~~~~~

Each test should be maximally independent of other tests. Do not leave files
laying around after your test has finished, and do not assume that some other
test has run beforehand. It's fine to use caching techniques to avoid repeated,
lengthy setup times.

Be Correct
~~~~~~~~~~

Tests should be as robust as possible, which at a basic level means using the
available frameworks correctly. All deferreds should have callbacks and be
chained properly. Error conditions should be checked properly. Race conditions
should not exist (see :ref:`Tests-Independent-of-Time`, above).

Be Helpful
~~~~~~~~~~

Note that tests will pass most of the time, but the moment when they are most
useful is when they fail.

When the test fails, it should produce output that is helpful to the person
chasing it down. This is particularly important when the tests are run
remotely, in which case the person chasing down the bug does not have access to
the system on which the test fails. A test which fails sporadically with no
more information than "AssertionFailed?" is a prime candidate for deletion if
the error isn't obvious. Making the error obvious also includes adding comments
describing the ways a test might fail.

Mixins
~~~~~~

Do not define setUp and tearDown directly in a mixin. This is the path to
madness. Instead, define a :func:`myMixinNameSetUp` and
:func:`myMixinNameTearDown`, and call them explicitly from the subclass's
:meth:`setUp` and :meth:`tearDown`. This makes it perfectly clear what is being
set up and torn down from a simple analysis of the test case.

Keeping State
~~~~~~~~~~~~~

Python does not allow assignment to anything but the innermost local scope or
the global scope with the ``global`` keyword.  This presents a problem when
creating nested functions::

    def test_localVariable(self):
        cb_called = False
        def cb():
            cb_called = True
        cb()
        self.assertTrue(cb_called) # will fail!

The ``cb_called = True`` assigns to a *different variable* than
``cb_called = False``.  In production code, it's usually best to work around
such problems, but in tests this is often the clearest way to express the
behavior under test.

The solution is to change something in a common mutable object.  While a simple
list can serve as such a mutable object, this leads to code that is hard to
read.  Instead, use :class:`State`::

    from buildbot.test.state import State
    
    def test_localVariable(self):
        state = State(cb_called=False)
        def cb():
            state.cb_called = True
        cb()
        self.assertTrue(state.cb_called) # passes

This is almost as readable as the first example, but it actually works. 

