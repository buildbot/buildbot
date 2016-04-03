Buildbot's Test Suite
=====================

Buildbot's tests are under ``buildbot.test`` and, for the buildslave,
``buildslave.test``.  Tests for the slave are similar to the master, although
in some cases helpful functionality on the master is not re-implemented on the
slave.

Suites
------

Tests are divided into a few suites:

* Unit tests (``buildbot.test.unit``) - these follow unit-testing practices and
  attempt to maximally isolate the system under test.  Unit tests are the main
  mechanism of achieving test coverage, and all new code should be well-covered
  by corresponding unit tests.

  * Interface tests are a special type of unit tests, and are found in the same directory and often the same file.
    In many cases, Buildbot has multiple implementations of the same interface -- at least one "real" implementation and a fake implementation used in unit testing.
    The interface tests ensure that these implementations all meet the same standards.
    This ensures consistency between implementations, and also ensures that the unit tests are testing against realistic fakes.

* Integration tests (``buildbot.test.integration``) - these test combinations
  of multiple units.  Of necessity, integration tests are incomplete - they
  cannot test every condition; difficult to maintain - they tend to be complex
  and touch a lot of code; and slow - they usually require considerable setup
  and execute a lot of code.  As such, use of integration tests is limited to a
  few, broad tests to act as a failsafe for the unit and interface tests.

* Regression tests (``buildbot.test.regressions``) - these test to prevent
  re-occurrence of historical bugs.  In most cases, a regression is better
  tested by a test in the other suites, or unlike to recur, so this suite tends
  to be small.

* Fuzz tests (``buildbot.test.fuzz``) - these tests run for a long time and
  apply randomization to try to reproduce rare or unusual failures.  The
  Buildbot project does not currently have a framework to run fuzz tests
  regularly.

Unit Tests
~~~~~~~~~~

Every code module should have corresponding unit tests.  This is not currently
true of Buildbot, due to a large body of legacy code, but is a goal of the
project.  All new code must meet this requirement.

Unit test modules are be named after the package or class they test, replacing
``.`` with ``_`` and omitting the ``buildbot_``. For example,
:file:`test_status_web_authz_Authz.py` tests the :class:`Authz` class in
:file:`buildbot/status/web/authz.py`. Modules with only one class, or a few
trivial classes, can be tested in a single test module. For more complex
situations, prefer to use multiple test modules.

Unit tests using renderables require special handling. The following example
shows how the same test would be written with the 'param' parameter and with the
same parameter as a renderable.::

    def test_param(self):
        f = self.ConcreteClass(param='val')
        self.assertEqual(f.param, 'val')

When the parameter is renderable, you need to instantiate the Class before you
can you renderables::

    def setUp(self):
        self.build = Properties(paramVal='val')

    @defer.inlineCallbacks
    def test_param_renderable(self):
        f = self.ConcreteClass(param=Interpolate('%(kw:rendered_val)s',
                               rendered_val=Property('paramVal'))
        yield f.start_instance(self.build)
        self.assertEqual(f.param, 'val')

Interface Tests
~~~~~~~~~~~~~~~

Interface tests exist to verify that multiple implementations of an interface
meet the same requirements.  Note that the name 'interface' should not be
confused with the sparse use of Zope Interfaces in the Buildbot code -- in this
context, an interface is any boundary between testable units.

Ideally, all interfaces, both public and private, should be tested.  Certainly,
any *public* interfaces need interface tests.

Interface tests are most often found in files named for the "real" implementation, e.g., :file:`test_db_changes.py`.
When there is ambiguity, test modules should be named after the interface they are testing.
Interface tests have the following form::

    from buildbot.test.util import interfaces
    from twistd.trial import unittest

    class Tests(interfaces.InterfaceTests):

        # define methods that must be overridden per implementation
        def someSetupMethod(self):
            raise NotImplementedError

        # method signature tests
        def test_signature_someMethod(self):
            @self.assertArgSpecMatches(self.systemUnderTest.someMethod)
            def someMethod(self, arg1, arg2):
                pass

        # tests that all implementations must pass
        def test_something(self):
            pass # ...

    class RealTests(Tests):

        # tests that only *real* implementations must pass
        def test_something_else(self):
            pass # ...

All of the test methods are defined here, segregated into tests that all implementations must pass, and tests that the fake implementation is not expected to pass.
The ``test_signature_someMethod`` test above illustrates the :py:func:`buildbot.test.util.interfaces.assertArgSpecMatches` decorator, which can be used to compare the argument specification of a callable with a reference signature conveniently written as a nested function.
Wherever possible, prefer to add tests to the ``Tests`` class, even if this means testing one method (e.g,. ``setFoo``) in terms of another (e.g., ``getFoo``).

The ``assertArgSpecMatches`` method can take multiple methods to test; it will check each one in turn.

At the bottom of the test module, a subclass is created for each implementation, implementing the setup methods that were stubbed out in the parent classes::

    class TestFakeThing(unittest.TestCase, Tests):

        def someSetupMethod(self):
            pass # ...

    class TestRealThing(unittest.TestCase, RealTests):

        def someSetupMethod(self):
            pass # ...

For implementations which require optional software, such as an AMQP server, this is the appropriate place to signal that tests should be skipped when their prerequisites are not available.

Integration Tests
~~~~~~~~~~~~~~~~~

Integration test modules test several units at once, including their
interactions.  In general, they serve as a catch-all for failures and bugs that
were not detected by the unit and interface tests.  As such, they should not
aim to be exhaustive, but merely representative.

Integration tests are very difficult to maintain if they reach into the
internals of any part of Buildbot.  Where possible, try to use the same means
as a user would to set up, run, and check the results of an integration test.
That may mean writing a :file:`master.cfg` to be parsed, and checking the
results by examining the database (or fake DB API) afterward.

Regression Tests
~~~~~~~~~~~~~~~~

Regression tests are even more rare in Buildbot than integration tests.  In
many cases, a regression test is not necessary -- either the test is
better-suited as a unit or interface test, or the failure is so specific that a
test will never fail again.

Regression tests tend to be closely tied to the code in which the error
occurred.  When that code is refactored, the regression test generally becomes
obsolete, and is deleted.

Fuzz Tests
~~~~~~~~~~

Fuzz tests generally run for a fixed amount of time, running randomized tests
against a system.  They do not run at all during normal runs of the Buildbot
tests, unless ``BUILDBOT_FUZZ`` is defined. This is accomplished with something
like the following at the end of each test module::

    if 'BUILDBOT_FUZZ' not in os.environ:
        del LRUCacheFuzzer

Mixins
------

Buildbot provides a number of purpose-specific mixin classes in :src:`master/buildbot/util`.
These generally define a set of utility functions as well as ``setUpXxx`` and ``tearDownXxx`` methods.
These methods should be called explicitly from your subclass's ``setUp`` and ``tearDown`` methods.
Note that some of these methods return Deferreds, which should be handled properly by the caller.

.. _Fakes:

Fakes
-----

Buildbot provides a number of pre-defined fake implementations of internal interfaces, in :src:`master/buildbot/fake`.
These are designed to be used in unit tests to limit the scope of the test.
For example, the fake DB API eliminates the need to create a real database when testing code that uses the DB API, and isolates bugs in the system under test from bugs in the real DB implementation.

The danger of using fakes is that the fake interface and the real interface can
differ.  The interface tests exist to solve this problem.  All fakes should be
fully tested in an integration test, so that the fakes pass the same tests as
the "real" thing.  It is particularly important that the method signatures be
compared.

Type Validation
---------------

The :src:`master/buildbot/test/util/validation.py` provides a set of classes and definitions for validating Buildbot data types.
It supports four types of data:

 * DB API dictionaries, as returned from the ``getXxx`` methods,
 * Data API dictionaries, as returned from ``get``,
 * Data API messages, and
 * Simple data types.

These are validated from elsewhere in the codebase with calls to

 * ``verifyDbDict(testcase, type, value)``,
 * ``verifyData(testcase, type, options, value)``,
 * ``verifyMessage(testcase, routingKey, message)``, and
 * ``verifyType(testcase, name, value, validator)``.

respectively.
The ``testcase`` argument is used to fail the test case if the validation does not succeed.
For DB dictionaries and data dictionaries, the ``type`` identifies the expected data type.
For messages, the type is determined from the first element of the routing key.

All messages sent with the fake MQ implementation are automatically validated using ``verifyMessage``.
The ``verifyType`` method is used to validate simple types, e.g., ::

    validation.verifyType(self, 'param1', param1, validation.StringValidator())

In any case, if ``testcase`` is None, then the functions will raise an :py:exc:`AssertionError` on failure.

Validator Classes
~~~~~~~~~~~~~~~~~

A validator is an instance of the ``Validator`` class.
Its ``validate`` method is a generator function that takes a name and an object to validate.
It yields error messages describing any deviations of ``object`` from the designated data type.
The ``name`` argument is used to make such messages more helpful.

A number of validators are supplied for basic types.
A few classes deserve special mention:

 * ``NoneOk`` wraps another validator, allowing the object to be None.
 * ``Any`` will match any object without error.
 * ``IdentifierValidator`` will match identifiers; see :ref:`identifier <type-identifier>`.
 * ``DictValidator`` takes key names as keyword arguments, with the values giving validators for each key.
   The ``optionalNames`` argument is a list of keys which may be omitted without error.
 * ``SourcedPropertiesValidator`` matches dictionaries with (value, source) keys, the representation used for properties in the data API.
 * ``MessageValidator`` validates messages.
   It checks that the routing key is a tuple of strings.
   The first tuple element gives the message type.
   The last tuple element is the event, and must be a member of the ``events`` set.
   The remaining "middle" tuple elements must match the message values identified by ``keyFields``.
   The ``messageValidator`` should be a ``DictValidator`` configured to check the message body.
   This validator's ``validate`` method is called with a tuple ``(routingKey, message)``.
 * ``Selector`` allows different validators to be selected based on matching functions.
   Its ``add`` method takes a matching function, which should return a boolean, and a validator to use if the matching function returns true.
   If the matching function is None, it is used as a default.
   This class is used for message and data validation.

Defining Validators
~~~~~~~~~~~~~~~~~~~

DB validators are defined in the ``dbdict`` dictionary, e.g., ::

    dbdict['foodict'] = DictValidator(
        id=IntValidator(),
        name=StringValidator(),
        ...
    )

Data validators are ``Selector`` validators, where the selector is the ``options`` passed to ``verifyData``. ::

    data['foo'] = Selector()
    data['foo'].add(lambda opts : opt.get('fanciness') > 10,
        DictValidator(
            fooid=IntValidator(),
            name=StringValidator(),
            ...
    ))

Similarly, message validators are ``Selector`` validators, where the selector is the routing key.
The underlying validator should be a ``MessageValidator``. ::

    message['foo'] = Selector()
    message['foo'].add(lambda rk : rk[-1] == 'new',
        MessageValidator(
            keyFields=['fooid'],
            events=['new', 'complete'],
            messageValidator=DictValidator(
                fooid=IntValidator(),
                name=StringValidator(),
                ...
           )))

Good Tests
----------

Bad tests are worse than no tests at all, since they waste developers' time
wondering "was that a spurious failure?" or "what the heck is this test trying
to do?"  Buildbot needs good tests.  So what makes a good test?

.. _Tests-Independent-of-Time:

Independent of Time
~~~~~~~~~~~~~~~~~~~

Tests that depend on wall time will fail. As a bonus, they run very slowly. Do
not use :meth:`reactor.callLater` to wait "long enough" for something to happen.

For testing things that themselves depend on time, consider using
:class:`twisted.internet.tasks.Clock`.  This may mean passing a clock instance to
the code under test, and propagating that instance as necessary to ensure that
all of the code using :meth:`callLater` uses it.  Refactoring code for
testability is difficult, but worthwhile.

For testing things that do not depend on time, but for which you cannot detect
the "end" of an operation: add a way to detect the end of the operation!

Clean Code
~~~~~~~~~~

Make your tests readable. This is no place to skimp on comments! Others will
attempt to learn about the expected behavior of your class by reading the
tests. As a side note, if you use a :class:`Deferred` chain in your test, write
the callbacks as nested functions, rather than using methods with funny names::

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

Test method names should follow the pattern :samp:`test_{METHOD}_{CONDITION}`
where *METHOD* is the method being tested, and *CONDITION* is the
condition under which it's tested. Since we can't always test a single
method, this is not a hard-and-fast rule.

Assert Only One Thing
~~~~~~~~~~~~~~~~~~~~~

Where practical, each test should have a single assertion. This may require a
little bit of work to get several related pieces of information into a single
Python object for comparison. The problem with multiple assertions is that, if
the first assertion fails, the remainder are not tested.  The test results then
do not tell the entire story.

Prefer Fakes to Mocks
~~~~~~~~~~~~~~~~~~~~~

Mock objects are too "compliant", and this often masks errors in the system
under test.  For example, a mis-spelled method name on a mock object will not
raise an exception.

Where possible, use one of the pre-written fake objects (see
:ref:`Fakes`) instead of a mock object.  Fakes
themselves should be well-tested using interface tests.

Where they are appropriate, Mock objects can be constructed easily using the
aptly-named `mock <http://www.voidspace.org.uk/python/mock/>`_ module, which is
a requirement for Buildbot's tests.

Small Tests
~~~~~~~~~~~

The shorter each test is, the better. Test as little code as possible in each test.

It is fine, and in fact encouraged, to write the code under test in such a way
as to facilitate this. As an illustrative example, if you are testing a new
Step subclass, but your tests require instantiating a BuildMaster, you're
probably doing something wrong!

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
available frameworks correctly. All Deferreds should have callbacks and be
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
more information than "AssertionFailed" is a prime candidate for deletion if
the error isn't obvious. Making the error obvious also includes adding comments
describing the ways a test might fail.

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
