.. _Concepts:

Concepts
========

This chapter defines some of the basic concepts that Buildbot uses.
You'll need to understand how Buildbot sees the world to configure it properly.

.. index: repository
.. index: codebase
.. index: project
.. index: revision
.. index: branch
.. index: source stamp

.. _Source-Stamps:

Source identification
---------------------

The following concepts are used within Buildbot to describe source code that is being built:

Repository
    A repository is a location where files tracked by a version control system reside.
    Usually, it is identified by a URL or a location on a disk.
    It contains a subset of the history of a codebase.

Codebase
    A codebase is a collection of related files and their history tracked as a unit by version control systems.
    The files and their history are stored in one or more repositories.
    For example, the primary repository for the Buildbot codebase is at ``https://github.com/buildbot/buildbot/``.
    There are also more than a thousand forks of Buildbot.
    These repositories, while storing potentially very old versions of Buildbot code, still contain the same codebase.

Project
    A project is a set of one or more codebases that together may be built and produce some end artifact.
    For example, an application may be comprised of two codebases - one for the code and one for the test data, the latter of which occupies a lot of space.
    Building and testing such an application requires acquiring code from both codebases.

Revision:
    A revision is an textual identifier used by most version control systems to uniquely specify a particular version of the source code in a particular codebase.

Source stamp:
    A source stamp is a collection of information needed to identify a particular version of code on a certain codebase.
    In most version control systems, source stamps only store a revision.
    On other version control systems, a branch is also required.

Source stamp set:
    A source stamp set is a set of source stamps to identify a particular version of code on a certain project.
    Like a project is a collection of codebases, a source stamp set is a collection of source stamps, one for each codebase within a project.

In order to build a project, Buildbot only needs to know a source stamp set corresponding to that project.
This source stamp set has a source stamp for each codebase comprising the project.
In turn, each source stamp has enough information to identify a particular version of the code within the codebase.

.. image:: ../_images/changes.*
   :alt: Source Stamp Sets

.. _Concepts-Change-Source:

Change sources
--------------

Change sources are user-configurable components that interact with external version control systems and retrieve new code.
Internally, new code is represented as :ref:`Changes <Concept-Change>` which roughly correspond to a single commit or changeset.
The changes are sent to the schedulers which then decide whether new builds should be created for these new code changes.

The design of Buildbot requires the workers to have their own copies of the source code, thus change sources is an optional component as long as there are no schedulers that create new builds based on new code commit events.


.. index: change

.. _Concept-Change:

Changes
-------

A :ref:`Change<Change-Attrs>` is an abstract way Buildbot uses to represent a single change to the source files, performed by a developer.
In version control systems that support the notion of atomic check-ins, a change represents a changeset or commit.

Changes are used for the :ref:`Change sources<Concepts-Change-Source>` to communicate with :ref:`Schedulers <Concepts-Scheduler>`.

A :class:`Change` comprises the following information:

 - the developer who is responsible for the change

 - the list of files that the change added, removed or modified

 - the message of the commit

 - the repository, the codebase and the project that the change corresponds to

 - the revision and the branch of the commit

.. _Concepts-Scheduler:

Schedulers
----------

A scheduler is a component that decides when to start a build.
The decision could be based on time, on new code being committed or on similar events.

Schedulers are responsible for creating :ref:`Build Requests<Concepts-Build-Request>` which identify a request to start a build on a specific version of the source code.

Each Buildmaster has a set of scheduler objects, each of which gets a copy of every incoming :class:`Change`.
The Schedulers are responsible for deciding when :class:`Build`\s should be run.
Some Buildbot installations might have a single scheduler, while others may have several, each for a different purpose.

.. _Concepts-Build-Request:

BuildRequests
-------------

A :class:`BuildRequest` is a request to start a specific build.
A :class:`BuildRequest` consists of the following information:

 - the name of the :class:`Builder` (see below) that will perform the build.

 - the set of :class:`SourceStamp`\s (see above) that specify the version of the source tree to build and/or test.

Two build requests representing the same version of the source code and the same builder may be merged.
The user may configure additional restrictions for determining mergeability of build requests.

.. _Concepts-Builder:

.. _Concepts-Build-Factories:

Builders and Build Factories
----------------------------

A :class:`Builder` is responsible for creating new builds from :class:`BuildRequest`\s.
Creating a new build is essentially determining the following properties of the subsequent build:

 - the exact :ref:`steps <Concepts-Step>` a build will execute

 - the :ref:`workers <Concepts-Worker>` that the build may run on

The sequence of steps to run is performed by user-configurable :class:`BuildFactory` that is attached to each :class:`Builder` by the user.

A :class:`Builder` will attempt to create a :class:`Build` from a :class:`BuildRequest` as soon as it is possible, that is, as soon as the associated worker becomes free.
When a worker becomes free, the build master will select the oldest :class:`BuildRequest` that can run on that worker and notify the corresponding :class:`Builder` to maybe start a build out of it.

Each :class:`Builder` by default runs completely independently.
This means, that a worker that has N builders attached to it, may potentially attempt to run N builds concurrently.
This level of concurrency may be controlled by various kinds of :ref:`Interlocks`.

At a low level, each builder has its own exclusive directory on the build master and one exclusive directory on each of the workers it is attached to.
The directory on the master is used for keeping status information.
The directories on the workers are used as a location where the actual checkout, compilation and testing steps happen.

.. _Concepts-Build:

.. _Concepts-Step:

Builds
------

A :class:`Build` represents a single compile or test run of a particular version of a source code.
A build is comprised of a series of steps.
The steps may be arbitrary. For example, for compiled software a build generally consists of the checkout, configure, make, and make check sequence.
For interpreted projects like Python modules, a build is generally a checkout followed by an invocation of the bundled test suite.

Builds are created by instances of :class:`Builder` (see above).

.. _Concepts-BuildSet:

BuildSets
---------

A :class:`BuildSet` represents a set of potentially not yet created :class:`Build`\s that all compile and/or test the same version of the source tree.
It tracks whether this set of builds as a whole succeeded or not.
The information that is stored in a BuildSet is a set of :class:`SourceStamp`\s which define the version of the code to test and a set of :class:`Builder`\s which define what builds to create.

.. _Concepts-Worker:

Workers
-------

A :class:`Worker` corresponds to an environment where builds are executed.
A single physical machine must run at least one :class:`Worker` in order for Buildbot to be able to utilize it for running builds.
Multiple :class:`Worker`\s may run on a single machine to provide different environments that can reuse the same hardware by means of containers or virtual machines.

Each builder is associated with one or more :class:`Worker`\s.
For example, a builder which is used to perform macOS builds (as opposed to Linux or Windows builds) should naturally be associated with a Mac worker.

If multiple workers are available for any given builder, you will have some measure of redundancy: in case one worker goes offline, the others can still keep the :class:`Builder` working.
In addition, multiple workers will allow multiple simultaneous builds for the same :class:`Builder`, which might be useful if you have a lot of forced or ``try`` builds taking place.

Ideally, each :class:`Worker` that is configured for a builder should be identical.
Otherwise build or test failures will be dependent on which worker the build is run and this will complicate investigations of failures.

.. _Concepts-Users:

Users
-----

Buildbot has a somewhat limited awareness of *users*.
It assumes the world consists of a set of developers, each of whom can be described by a couple of simple attributes.
These developers make changes to the source code, causing builds which may succeed or fail.

Users also may have different levels of authorization when issuing Buildbot commands, such as forcing a build from the web interface or from an IRC channel.

Each developer is primarily known through the source control system.
Each :class:`Change` object that arrives is tagged with a :attr:`who` field that typically gives the account name (on the repository machine) of the user responsible for that change.
This string is displayed on the HTML status pages and in each :class:`Build`\'s *blamelist*.

To do more with the User than just refer to them, this username needs to be mapped into an address of some sort.
The responsibility for this mapping is left up to the status module which needs the address.
In the future, the responsibility for managing users will be transferred to User Objects.

The ``who`` fields in ``git`` Changes are used to create :ref:`User-Objects`, which allows for more control and flexibility in how Buildbot manages users.

.. _User-Objects:

User Objects
~~~~~~~~~~~~

User Objects allow Buildbot to better manage users throughout its various interactions with users (see :ref:`Change-Sources` and :ref:`Reporters`).
The User Objects are stored in the Buildbot database and correlate the various attributes that a user might have: irc, Git, etc.

Changes
+++++++

Incoming Changes all have a ``who`` attribute attached to them that specifies which developer is responsible for that Change.
When a Change is first rendered, the ``who`` attribute is parsed and added to the database, if it doesn't exist, or checked against an existing user.
The ``who`` attribute is formatted in different ways depending on the version control system that the Change came from.

``git``
    ``who`` attributes take the form ``Full Name <Email>``.

``svn``
    ``who`` attributes are of the form ``Username``.

``hg``
    ``who`` attributes are free-form strings, but usually adhere to similar conventions as ``git`` attributes (``Full Name <Email>``).

``cvs``
    ``who`` attributes are of the form ``Username``.

``darcs``
    ``who`` attributes contain an ``Email`` and may also include a ``Full Name`` like ``git`` attributes.

``bzr``
    ``who`` attributes are free-form strings like ``hg``, and can include a ``Username``, ``Email``, and/or ``Full Name``.

Tools
+++++

For managing users manually, use the ``buildbot user`` command, which allows you to add, remove, update, and show various attributes of users in the Buildbot database (see :ref:`Command-line-Tool`).

Uses
++++

Correlating the various bits and pieces that Buildbot views as users also means that one attribute of a user can be translated into another.
This provides a more complete view of users throughout Buildbot.

One such use is being able to find email addresses based on a set of Builds to notify users through the ``MailNotifier``.
This process is explained more clearly in :ref:`Email-Addresses`.

Another way to utilize `User Objects` is through `UsersAuth` for web authentication.
To use `UsersAuth`, you need to set a `bb_username` and `bb_password` via the ``buildbot user`` command line tool to check against.
The password will be encrypted before it gets stored in the database along with other user attributes.

.. _Doing-Things-With-Users:

Doing Things With Users
~~~~~~~~~~~~~~~~~~~~~~~

Each change has a single user who is responsible for it.
Most builds have a set of changes: the build generally represents the first time these changes have been built and tested by the Buildbot.
The build has a *blamelist* that is the union of the users responsible for all of the build's changes.
If the build was created by a :ref:`Try-Schedulers` this list will include the submitter of the try job if known.

The build provides a list of users who are interested in the build -- the *interested users*.
Usually this is equal to the blamelist, but may also be expanded, e.g., to include the current build sherrif or a module's maintainer.

If desired, buildbot can notify the interested users until the problem is resolved.

.. _Email-Addresses:

Email Addresses
~~~~~~~~~~~~~~~

The :bb:reporter:`MailNotifier` is a status target which can send emails about the results of each build.
It accepts a static list of email addresses to which each message should be delivered, but it can also be configured to send emails to a :class:`Build`\'s Interested Users.
To do this, it needs a way to convert User names into email addresses.

For many VCSs, the User name is actually an account name on the system which hosts the repository.
As such, turning the name into an email address is simply a matter of appending ``@repositoryhost.com``.
Some projects use other kinds of mappings (for example the preferred email address may be at ``project.org``, despite the repository host being named ``cvs.project.org``), and some VCSs have full separation between the concept of a user and that of an account on the repository host (like Perforce).
Some systems (like Git) put a full contact email address in every change.

To convert these names to addresses, the :class:`MailNotifier` uses an :class:`EmailLookup` object.
This provides a :meth:`getAddress` method which accepts a name and (eventually) returns an address.
The default :class:`MailNotifier` module provides an :class:`EmailLookup` which simply appends a static string, configurable when the notifier is created.
To create more complex behaviors (perhaps using an LDAP lookup, or using ``finger`` on a central host to determine a preferred address for the developer), provide a different object as the ``lookup`` argument.

If an EmailLookup object isn't given to the MailNotifier, the MailNotifier will try to find emails through :ref:`User-Objects`.
If every user in the Build's Interested Users list has an email in the database for them, this will work the same as if an EmailLookup object was used.
If a user whose change led to a Build doesn't have an email attribute, that user will not receive an email.
If ``extraRecipients`` is given, those users still get an email when the EmailLookup object is not specified.

In the future, when the Problem mechanism has been set up, Buildbot will need to send emails to arbitrary Users.
It will do this by locating a :class:`MailNotifier`\-like object among all the buildmaster's status targets, and asking it to send messages to various Users.
This means the User-to-address mapping only has to be set up once, in your :class:`MailNotifier`, and every email message buildbot emits will take advantage of it.

.. _IRC-Nicknames:

IRC Nicknames
~~~~~~~~~~~~~

Like :class:`MailNotifier`, the :class:`buildbot.reporters.irc.IRC` class provides a status target which can announce the results of each build.
It also provides an interactive interface by responding to online queries posted in the channel or sent as private messages.

In the future, buildbot can be configured to map User names to IRC nicknames, to watch for the recent presence of these nicknames, and to deliver build status messages to the interested parties.
Like :class:`MailNotifier` does for email addresses, the :class:`IRC` object will have an :class:`IRCLookup` which is responsible for nicknames.
The mapping can be set up statically, or it can be updated by online users themselves (by claiming a username with some kind of ``buildbot: i am user warner`` commands).

Once the mapping is established, buildbot can then ask the :class:`IRC` object to send messages to various users.
It can report on the likelihood that the user saw the given message (based upon how long the user has been inactive on the channel), which might prompt the Problem Hassler logic to send them an email message instead.

These operations and authentication of commands issued by particular nicknames will be implemented in :ref:`User-Objects`.

.. index:: Properties

.. _Build-Properties:

Build Properties
----------------

Each build has a set of *Build Properties*, which can be used by its build steps to modify their actions.

The properties are represented as a set of key-value pairs.
Effectively, a single property is a variable that, once set, can be used by subsequent steps in a build to modify their behaviour.
The value of a property can be a number, a string, a list or a dictionary.
Lists and dictionaries can contain other lists or dictionaries.
Thus, the value of a property could be any arbitrarily complex structure.

Properties work pretty much like variables, so they can be used to implement all manner of functionality.

The following are a couple of examples:

 - By default, the name of the worker that runs the build is set to the ``workername`` property.
   If there are multiple different workers and the actions of the build depend on the exact worker, some users may decide that it's more convenient to vary the actions depending on the ``workername`` property instead of creating separate builders for each worker.

 - In most cases, the build does not know the exact code revision that will be tested until it checks out the code.
   This information is only known after a :ref:`source step <Build-Steps>` runs.
   To give this information to the subsequent steps, the source step records the checked out revision into the ``got_revision`` property.
