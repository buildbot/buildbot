Developer Information
=====================

This chapter is the official repository for the collected wisdom of the
Buildbot hackers.

It contains some sparse documentation of the inner workings of Buildbot, but of
course, the final reference for that is the source itself.

More importantly, this chapter represents the official repository of all
agreed-on patterns for use in Buildbot.  In this case, the source is a
*terrible* reference, because much of it is old and crusty.  But we are
trying to do things the new, better way, and those new, better ways are
described here.

.. _Buildmaster-Service-Hierarchy:

Buildmaster Service Hierarchy
-----------------------------

Buildbot uses Twisted's service hierarchy heavily.  The hierarchy looks like
this:

.. py:class:: buildbot.master.BuildMaster

    This is the top-level service.

    .. py:class:: buildbot.master.BotMaster

        The :class:`BotMaster` manages all of the slaves.  :class:`BuildSlave` instances are added as
        child services of the :class:`BotMaster`.
    
    .. py:class:: buildbot.changes.manager.ChangeManager
    
        The :class:`ChangeManager` manages the active change sources, as well as the stream of
        changes received from those sources.
    
    .. py:class:: buildbot.schedulers.manager.SchedulerManager
    
        The :class:`SchedulerManager` manages the active schedulers and handles inter-scheduler
        notifications.
    
    :class:`IStatusReceiver` implementations
        Objects from the ``status`` configuration key are attached directly to the
        buildmaster. These classes should inherit from :class:`StatusReceiver` or
        :class:`StatusReceiverMultiService` and include an
        ``implements(IStatusReceiver)`` stanza.


.. _Access-to-Configuration:

Access to Configuration
-----------------------

The master object makes much of the configuration available from an object
named ``master.config``.  Configuration is stored as attributes of this
object.  Where possible, components should access this configuration directly
and not cache the configuration values anywhere else.  This avoids the need to
ensure that update-from-configuration methods are called on a reconfig.

The available attributes are listed in the docstring for the
:class:`buildbot.config.MasterConfig` class.

.. _Utilities:
        
Utilities
---------

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

The Database
------------

.. py:class:: buildbot.db.connector.DBConnector

TODO

.. _Database-Schema:

Database Schema
~~~~~~~~~~~~~~~

.. py:class:: buildbot.db.schema.DBSchemaManager

The SQL for the database schema is available in
:file:`buildbot/db/schema/tables.sql`.  However, note that this file is not used
for new installations or upgrades of the Buildbot database.

Instead, the :class:`buildbot.db.schema.DBSchemaManager` handles this task.  The
operation of this class centers around a linear sequence of database versions.
Versions start at 0, which is the old pickle-file format.  The manager has
methods to query the version of the database, and the current version from the
source code.  It also has an :meth:`upgrade` method which will upgrade the
database to the latest version.  This operation is currently irreversible.

There is no operation to "install" the latest schema.  Instead, a fresh install
of buildbot begins with an (empty) version-0 database, and upgrades to the
current version.  This trades a bit of efficiency at install time for
assurances that the upgrade code is well-tested.

.. _Changing-the-Schema:

Changing the Schema
~~~~~~~~~~~~~~~~~~~

To make a change to the database schema, follow these steps:

 1. Increment ``CURRENT_VERSION`` in :file:`buildbot/db/schema/manager.py` by
     one.  This is your new version number.

 2. Create :file:`buildbot/db/schema/v{N}.py`, where *N* is your version number, by
    copying the previous script and stripping it down.  This script should define a
    subclass of :class:`buildbot.db.schema.base.Updater` named ``Updater``. 
    
    The class must define the method :meth:`upgrade`, which takes no arguments.  It
    should upgrade the database from the previous version to your version,
    including incrementing the number in the ``VERSION`` table, probably with an
    ``UPDATE`` query.
    
    Consult the API documentation for the base class for information on the
    attributes that are available.

 3. Edit :file:`buildbot/test/unit/test_db_schema_master.py`.  If your upgrade
    involves moving data from the basedir into the database proper, then edit
    :meth:`fill_basedir` to add some test data.
    
    Add code to :meth:`assertDatabaseOKEmpty` to check that your upgrade works on an
    empty database.
    
    Add code to :meth:`assertDatabaseOKFull` to check that your upgrade works on a
    database with pre-existing data.  Do this even if your changes do not move any
    data from the basedir.
    
    Run the tests to find the bugs you introduced in step 2.

 4. Increment the version number in the ``test_get_current_version`` test in the
    same file.  Only do this after you've finished the previous step - a failure of
    this test is a good reminder that testing isn't done yet.


 5. Updated the version number in :file:`buildbot/db/schema/tables.sql`, too.

 6. Finally, make the corresponding changes to :file:`buildbot/db/schema/tables.sql`.

.. _Log-File-Format:

Log File Format
---------------

.. py:class:: buildbot.status.logfile.LogFile

The master currently stores each logfile in a single file, which may have a
standard compression applied.

The format is a special case of the netstrings protocol - see
http://cr.yp.to/proto/netstrings.txt.  The text in each netstring
consists of a one-digit channel identifier followed by the data from that
channel.

The formatting is implemented in the LogFile class in
:file:`buildbot/status/logfile.py`, and in particular by the :meth:`merge`
method.


Web Status
----------

.. _Jinja-Web-Templates:

Jinja Web Templates
~~~~~~~~~~~~~~~~~~~

Buildbot uses Jinja2 to render its web interface.  The authoritative source for
this templating engine is
`its own documentation <http://jinja.pocoo.org/2/documentation/>`_,
of course, but a few notes are in order for those who are
making only minor modifications.

Whitespace
++++++++++

Jinja directives are enclosed in ``{% .. %}``, and sometimes also have
dashes.  These dashes strip whitespace in the output.  For example:

.. code-block:: none

    {% for entry in entries %}
      <li>{{ entry }}</li>
    {% endfor %}

will produce output with too much whitespace:

.. code-block:: html

  <li>pigs</li>


  <li>cows</li>


But adding the dashes will collapse that whitespace completely:

.. code-block:: none

    {% for entry in entries -%}
      <li>{{ entry }}</li>
    {%- endfor %}

yields

.. code-block:: html

    <li>pigs</li><li>cows</li>

.. _Web-Authorization-Framework:
    
Web Authorization Framework
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Whenever any part of the web framework wants to perform some action on the
buildmaster, it should check the user's authorization first.

Always check authorization twice: once to decide whether to show the option to
the user (link, button, form, whatever); and once before actually performing
the action.

To check whether to display the option, you'll usually want to pass an authz
object to the Jinja template in your :class:`HtmlResource` subclass::

    def content(self, req, cxt):
        # ...
        cxt['authz'] = self.getAuthz(req)
        template = ...
        return template.render(**cxt)

and then determine whether to advertise the action in the template:

.. code-block:: none

    {{ if authz.advertiseAction('myNewTrick') }}
      <form action="{{ myNewTrick_url }}"> ...
    {{ endif }}

Actions can optionally require authentication, so use ``needAuthForm`` to
determine whether to require a 'username' and 'passwd' field in the generated
form.  These fields are usually generated by the :meth:`auth()` form:

.. code-block:: none

    {% if authz.needAuthForm('myNewTrick') %}
      {{ auth() }}
    {% endif %}

Once the POST request comes in, it's time to check authorization again.
This usually looks something like ::

    d = self.getAuthz(req).actionAllowed('myNewTrick', req, someExtraArg)
    wfd = defer.waitForDeferred(d)
    yield wfd
    res = wfd.getResult()
    if not res:
        yield Redirect(path_to_authfail(req))
        return

The ``someExtraArg`` is optional (it's handled with ``*args``, so you can
have several if you want), and is given to the user's authorization function.
For example, a build-related action should pass the build status, so that the
user's authorization function could ensure that devs can only operate on their
own builds.

Note that ``actionAllowed`` returns a ``Deferred`` instance, so you must wait
for the ``Deferred`` and yield the ``Redirect`` instead of returning it.

The available actions are listed in :ref:`WebStatus-Configuration-Parameters`.


.. _Obfuscating-Passwords:

Obfuscating Passwords
---------------------

.. py:class:: buildslave.util.Obfuscated

It's often necessary to pass passwords to commands on the slave, but it's no
fun to see those passwords appear for everyone else in the build log.  The
:class:`Obfuscated` class can help here.  Instantiate it with a real string and a
fake string that should appear in logfiles.  You can then use the
:meth:`Obfuscated.get_real` and :meth:`Obfuscated.get_fake` static methods to
convert a list of command words to the real or fake equivalent.

The ``RunProcess`` implementation in the buildslave will apply these methods
automatically, so just feed it a list of strings and :class:`Obfuscated` objects.

.. _Master-Slave-API:

Master-Slave API
----------------

This section is a (very incomplete) description of the master-slave interface.
The interface is based on Twisted's Perspective Broker.

Connection
~~~~~~~~~~

The slave connects to the master, using the parameters supplied to
:command:`buildslave create-slave`.  It uses a reconnecting process with an
exponential backoff, and will automatically reconnect on disconnection.

.. py:class:: buildslave.bot.Bot

Once connected, the slave authenticates with the Twisted Cred (newcred)
mechanism, using the username and password supplied to :command:`buildslave
create-slave`.  The *mind* is the slave bot instance (class
:class:`buildslave.bot.Bot`).

.. py:class:: buildbot.master.Dispatcher
.. py:class:: buildbot.buildslave.BuildSlave

On the master side, the realm is implemented by
:class:`buildbot.master.Dispatcher`, which examines the username of incoming
avatar requests.  There are special cases for ``change``, ``debug``, and
``statusClient``, which are not discussed here.  For all other usernames,
the botmaster is consulted, and if a slave with that name is configured, its
:class:`buildbot.buildslave.BuildSlave` instance is returned as the perspective.

Build Slaves
~~~~~~~~~~~~

At this point, the master-side BuildSlave object has a pointer to the remote,
slave-side Bot object in ``self.slave``, and the slave-side Bot object has a
reference to the master-side BuildSlave object in ``self.perspective``.

Bot methods
+++++++++++

The slave-side object has the following remote methods:


:meth:`remote_getCommands`
    Returns a list of ``(name, version)`` for all commands the slave recognizes

:meth:`remote_setBuilderList`
    Given a list of builders and their build directories, ensures that
    those builders, and only those builders, are running.  This can be
    called after the initial connection is established, with a new
    list, to add or remove builders.

    This method returns a dictionary of :class:`SlaveBuilder` objects - see below

:meth:`remote_print`
    Adds a message to the slave logfile

:meth:`remote_getSlaveInfo`
    Returns the contents of the slave's :file:`info/` directory. Also contains the keys


    ``environ``
        copy of the slaves environment
    ``system``
        OS the slave is running (extracted from pythons os.name)
    ``basedir``
        base directory where slave is running

:meth:`remote_getVersion`
    Returns the slave's version

BuildSlave methods
++++++++++++++++++

The master-side object has the following method:


:meth:`perspective_keepalive`
    Does nothing - used to keep traffic flowing over the TCP connection

Slave Builders
~~~~~~~~~~~~~~

.. py:class:: buildslave.bot.SlaveBuilder
.. py:class:: buildbot.process.builder.Builder
.. py:class:: buildbot.process.slavebuilder.SlaveBuilder

Each build slave has a set of builders which can run on it.  These are represented
by distinct classes on the master and slave, just like the BuildSlave and Bot objects
described above.

On the slave side, builders are represented as instances of the
:class:`buildslave.bot.SlaveBuilder` class.  On the master side, they are
represented by the :class:`buildbot.process.slavebuilder.SlaveBuilder` class.  The
following will refer to these as the slave-side and master-side SlaveBuilder
classes.  Each object keeps a reference to its opposite in ``self.remote``.

slave-side SlaveBuilder methods
+++++++++++++++++++++++++++++++

:meth:`remote_setMaster`
    Provides a reference to the master-side SlaveBuilder

:meth:`remote_print`
    Adds a message to the slave logfile; used to check round-trip connectivity

:meth:`remote_startBuild`
    Indicates that a build is about to start, and that any subsequent
    commands are part of that build

:meth:`remote_startCommand`
    Invokes a command on the slave side

:meth:`remote_interruptCommand`
    Interrupts the currently-running command

:meth:`remote_shutdown`
    Shuts down the slave cleanly

master-side SlaveBuilder methods
++++++++++++++++++++++++++++++++

The master side does not have any remotely-callable methods.

Setup
~~~~~

After the initial connection and trading of a mind (Bot) for an avatar
(BuildSlave), the master calls the Bot's :meth:`setBuilderList` method to set up
the proper slave builders on the slave side.  This method returns a reference to
each of the new slave-side SlaveBuilder objects.  Each of these is handed to the
corresponding master-side SlaveBuilder object.  This immediately calls the remote
:meth:`setMaster` method, then the :meth:`print` method.

Pinging
~~~~~~~

To ping a remote SlaveBuilder, the master calls the :meth:`print` method.

Building
~~~~~~~~

When a build starts, the msater calls the slave's :meth:`startBuild` method.
Each BuildStep instance will subsequently call the :meth:`startCommand` method,
passing a reference to itself as the ``stepRef`` parameter.  The
:meth:`startCommand` method returns immediately, and the end of the command is
signalled with a call to a method on the master-side BuildStep object.

master-side BuildStep methods
+++++++++++++++++++++++++++++

:meth:`remote_update`
    Update information about the running command.  See below for the format.

:meth:`remote_complete`
    Signal that the command is complete, either successfully or with a Twisted failure.

Updates from the slave are a list of individual update elements.  Each update
element is, in turn, a list of the form ``[data, 0]`` where the 0 is present
for historical reasons.  The data is a dictionary, with keys describing the
contents, e.g., ``header``, ``stdout``, or the name of a logfile.  If the
key is ``rc``, then the value is the exit status of the command.  No further
updates should be sent after an ``rc``.


.. _Twisted-Idioms:

Twisted Idioms
--------------

.. _Helpful-Twisted-Classes:

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

.. _Buildbot-Tests:
    
Buildbot Tests
--------------

.. _Toward-Better-Buildbot-Tests:

Toward Better Buildbot Tests
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

In general, we are trying to ensure that new tests are *good*.  So what makes
a good test?

.. _Independent-of-Time:

Independent of Time
+++++++++++++++++++

Tests that depend on wall time will fail. As a bonus, they run very slowly. Do
not use :meth:`reactor.callLater` to wait "long enough" for something to happen.

For testing things that themselves depend on time, consider using
:class:`twisted.internet.tasks.Clock`.  This may mean passing a clock instance to
the code under test, and propagating that instance as necessary to ensure that
all of the code using :meth:`callLater` uses it.  Refactoring code for
testability is difficult, but wortwhile.

For testing things that do not depend on time, but for which you cannot detect
the "end" of an operation: add a way to detect the end of the operation!

.. _Clean-Code:

Clean Code
++++++++++

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

.. _Good-Name:

Good Name
+++++++++

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

.. _Assert-Only-One-Thing:

Assert Only One Thing
+++++++++++++++++++++

Each test should have a single assertion. This may require a little bit of work
to get several related pieces of information into a single Python object for
comparison. The problem with multiple assertions is that, if the first
assertion fails, the remainder are not tested.  The test results then do not
tell the entire story.

If you need to make two unrelated assertions, you should be running two tests.

.. _Use-Mocks-and-Stubs:

Use Mocks and Stubs
+++++++++++++++++++

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

.. _Small-Tests:

Small Tests
+++++++++++

The shorter each test is, the better. Test as little code as possible in each test.

It is fine, and in fact encouraged, to write the code under test in such a way
as to facilitate this. As an illustrative example, if you are testing a new
Step subclass, but your tests require instantiating a BuildMaster, you're
probably doing something wrong! (Note that this rule is almost universally
violated in the existing buildbot tests).

This also applies to test modules.  Several short, easily-digested test modules
are preferred over a 1000-line monster.

.. _Isolation:

Isolation
+++++++++

Each test should be maximally independent of other tests. Do not leave files
laying around after your test has finished, and do not assume that some other
test has run beforehand. It's fine to use caching techniques to avoid repeated,
lengthy setup times.

.. _Be-Correct:

Be Correct
++++++++++

Tests should be as robust as possible, which at a basic level means using the
available frameworks correctly. All deferreds should have callbacks and be
chained properly. Error conditions should be checked properly. Race conditions
should not exist (see :ref:`Independent-of-Time`, above).

.. _Be-Helpful:

Be Helpful
++++++++++

Note that tests will pass most of the time, but the moment when they are most
useful is when they fail.

When the test fails, it should produce output that is helpful to the person
chasing it down. This is particularly important when the tests are run
remotely, in which case the person chasing down the bug does not have access to
the system on which the test fails. A test which fails sporadically with no
more information than "AssertionFailed?" is a prime candidate for deletion if
the error isn't obvious. Making the error obvious also includes adding comments
describing the ways a test might fail.

.. _Mixins:

Mixins
++++++

Do not define setUp and tearDown directly in a mixin. This is the path to
madness. Instead, define a :func:`myMixinNameSetUp` and
:func:`myMixinNameTearDown`, and call them explicitly from the subclass's
:meth:`setUp` and :meth:`tearDown`. This makes it perfectly clear what is being
set up and torn down from a simple analysis of the test case.

.. _Keeping-State-in-Tests:

Keeping State in Tests
~~~~~~~~~~~~~~~~~~~~~~

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

.. _Better-Debugging-through-Monkeypatching:

Better Debugging through Monkeypatching
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
.. @dvindex buildbot.test.util.monkeypatches

The module :mod:`buildbot.test.util.monkeypatches` contains a few
monkey-patches to Twisted that detect errors a bit better.  These patches
shouldn't affect correct behavior, so it's worthwhile including something like
this in the header of every test file::

    from buildbot.test.util.monkeypatches import monkeypatch
    monkeypatch()


.. _String-Encodings:

String Encodings
~~~~~~~~~~~~~~~~

Buildbot expects all strings used internally to be valid Unicode strings - not
bytestrings.

Note that Buildbot rarely feeds strings back into external tools in such a way
that those strings must match.  For example, Buildbot does not attempt to
access the filenames specified in a Change.  So it is more important to store
strings in a manner that will be most useful to a human reader (e.g., in
logfiles, web status, etc.) than to store them in a lossless format.

Inputs
++++++

On input, strings should be decoded, if their encoding is known.  Where
necessary, the assumed input encoding should be configurable.  In some cases,
such as filenames, this encoding is not known or not well-defined (e.g., a
utf-8 encoded filename in a latin-1 directory).  In these cases, the input
mechanisms should make a best effort at decoding, and use e.g., the
``errors='replace'`` option to fail gracefully on un-decodable characters.

Outputs
+++++++

At most points where Buildbot outputs a string, the target encoding is known.
For example, the web status can encode to utf-8.  In cases where it is not
known, it should be configurable, with a safe fallback (e.g., ascii with
``errors='replace'``.

.. _Metrics:

Metrics
~~~~~~~

New in buildbot 0.8.4 is support for tracking various performance
metrics inside the buildbot master process. Currently these are logged
periodically according to the ``log_interval`` configuration
setting of the @ref{Metrics Options} configuration.

If :ref:`WebStatus` is enabled, the metrics data is also available
via ``/json/metrics``. 

The metrics subsystem is implemented in
:mod:`buildbot.process.metrics`. It makes use of twisted's logging
system to pass metrics data from all over buildbot's code to a central
:class:`MetricsLogObserver` object, which is available at
``BuildMaster.metrics`` or via ``Status.getMetrics()``.

.. _Metric-Events:

Metric Events
+++++++++++++

:class:`MetricEvent` objects represent individual items to
monitor. There are three sub-classes implemented:


:class:`MetricCountEvent`
    Records incremental increase or decrease of some value, or an
    absolute measure of some value. ::


        from buildbot.process.metrics import MetricCountEvent

        # We got a new widget!
        MetricCountEvent.log('num_widgets', 1)

        # We have exactly 10 widgets
        MetricCountEvent.log('num_widgets', 10, absolute=True)

:class:`MetricTimeEvent`
    Measures how long things take. By default the average of the last
    10 times will be reported. ::

        from buildbot.process.metrics import MetricTimeEvent

        # function took 0.001s
        MetricTimeEvent.log('time_function', 0.001)

:class:`MetricAlarmEvent`
    Indicates the health of various metrics. ::

        from buildbot.process.metrics import MetricAlarmEvent, ALARM_OK

        # num_slaves looks ok
        MetricAlarmEvent.log('num_slaves', level=ALARM_OK)

.. _Metric-Handlers:

Metric Handlers
+++++++++++++++

:class:`MetricsHandler` objects are responsble for collecting
:class:`MetricEvent`\s of a specific type and keeping track of their
values for future reporting. There are :class:`MetricsHandler` classes
corresponding to each of the :class:`MetricEvent` types. 

.. _Metric-Watchers:

Metric Watchers
+++++++++++++++

Watcher objects can be added to :class:`MetricsHandlers` to be called
when metric events of a certain type are received. Watchers are
generally used to record alarm events in response to count or time
events. 

.. _Metric-Helpers:

Metric Helpers
++++++++++++++

:func:`countMethod(name)`
    A function decorator that counts how many times the function is
    called. ::

        from buildbot.process.metrics import countMethod

        @countMethod('foo_called')
        def foo():
            return "foo!"

:func:`Timer(name)`
    :class:`Timer` objects can be used to make timing events
    easier. When ``Timer.stop()`` is called, a
    :class:`MetricTimeEvent` is logged with the elapsed time since
    ``timer.start()`` was called. ::

        from buildbot.process.metrics import Timer

        def foo():
            t = Timer('time_foo')
            t.start()
            try:
                for i in range(1000):
                    calc(i)
                return "foo!"
            finally:
                t.stop()

    :class:`Timer` objects also provide a pair of decorators,
    :func:`startTimer`/\ :func:`stopTimer` to decorate other functions. ::

        from buildbot.process.metrics import Timer

        t = Timer('time_thing')

        @t.startTimer
        def foo():
            return "foo!"
    
        @t.stopTimer
        def bar():
            return "bar!"

        foo()
        bar()

:func:`timeMethod(name)`
    A function decorator that measures how long a function takes to
    execute. Note that many functions in buildbot return deferreds, so
    may return before all the work they set up has completed. Using an
    explicit :class:`Timer` is better in this case. ::

        from buildbot.process.metrics import timeMethod

        @timeMethod('time_foo')
        def foo():
            for i in range(1000):
                calc(i)
            return "foo!"

