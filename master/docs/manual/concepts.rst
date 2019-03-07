Concepts
========

This chapter defines some of the basic concepts that the Buildbot uses.
You'll need to understand how the Buildbot sees the world to configure it properly.

.. index: repository
.. index: codebase
.. index: project
.. index: revision
.. index: branch
.. index: source stamp

.. _Source-Stamps:

Source Stamps
-------------

Buildbot uses the concept of *source stamp set* to identify exact source code that needs to be built for a certain project.
A *source stamp set* is a collection of one or more source stamps.

A *source stamp* is a collection of information needed to identify a particular version of code on a certain codebase. This information most often is a revision and possibly a branch.

A *codebase* is a collection of related files and their history tracked as a unit by version control systems.
A single codebase may appear in multiple repositories which themselves are identified by URLs.
For example, ``https://github.com/mozilla/mozilla-central`` and ``http://hg.mozilla.org/mozilla-release`` both contain the Firefox codebase, although not exactly the same code.

A *project* corresponds to a set of one or more codebases that together may be built and produce some end artifact.
For example, a company may build several applications based on the same core library.
The "app" codebase and the "core" codebase are in separate repositories, but are compiled together and constitute a single project.
Changes to either codebase should cause a rebuild of the application.

A *revision* is an identifier used by most version control systems to uniquely specify a particular version of the source code.
Sometimes in order to do that a revision may make sense only if used in combination with a *branch*.

To sum up the above, to build a project, Buildbot needs to know exactly which version of each codebase it should build.
It uses a *source stamp* to do so for each codebase, each of which informs Buildbot that it should use a specific *revision* from that codebase.
Collectively these source stamps are called *source stamp set* for each project.

.. image:: _images/changes.*
   :alt: Source Stamp Sets

.. _Version-Control-Systems:

Version Control Systems
-----------------------

Buildbot supports a significant number of version control systems, so it treats them abstractly.

For purposes of deciding when to perform builds, Buildbot's change sources monitor repositories, and represent any updates to those repositories as *changes*.
These change sources fall broadly into two categories: pollers which periodically check the repository for updates; and hooks, where the repository is configured to notify Buildbot whenever an update occurs.
For more information see :ref:`Change-Sources` and :ref:`How-Different-VC-Systems-Specify-Sources`.

When it comes time to actually perform a build, a scheduler prepares a source stamp set, as described above, based on its configuration.
When the build begins, one or more source steps use the information in the source stamp set to actually check out the source code, using the normal VCS commands.

.. index: change

.. _Concept-Changes:

Changes
-------

A :ref:`Change<Change-Attrs>` is an abstract way Buildbot uses to represent a single change to the source files performed by a developer.
In version control systems that support the notion of atomic check-ins a change represents a changeset or commit.

A :class:`Change` comprises the following information:

 - the developer that is responsible for the change

 - the list of files that the change added, removed or modified

 - the message of the commit

 - the repository, the codebase and the project that the change corresponds to

 - the revision and the branch of the commit

.. _Scheduling-Builds:

Scheduling Builds
-----------------

Each Buildmaster has a set of scheduler objects, each of which gets a copy of every incoming :class:`Change`.
The Schedulers are responsible for deciding when :class:`Build`\s should be run.
Some Buildbot installations might have a single scheduler, while others may have several, each for a different purpose.

For example, a *quick* scheduler might exist to give immediate feedback to developers, hoping to catch obvious problems in the code that can be detected quickly.
These typically do not run the full test suite, nor do they run on a wide variety of platforms.
They also usually do a VC update rather than performing a brand-new checkout each time.

A separate *full* scheduler might run more comprehensive tests, to catch more subtle problems.
It might be configured to run after the quick scheduler, to give developers time to commit fixes to bugs caught by the quick scheduler before running the comprehensive tests.
This scheduler would also feed multiple :class:`Builder`\s.

Many schedulers can be configured to wait a while after seeing a source-code change - this is the *tree stable timer*.
The timer allows multiple commits to be "batched" together.
This is particularly useful in distributed version control systems, where a developer may push a long sequence of changes all at once.
To save resources, it's often desirable only to test the most recent change.

Schedulers can also filter out the changes they are interested in, based on a number of criteria.
For example, a scheduler that only builds documentation might skip any changes that do not affect the documentation.
Schedulers can also filter on the branch to which a commit was made.

There is some support for configuring dependencies between builds - for example, you may want to build packages only for revisions which pass all of the unit tests.
This support is under active development in Buildbot, and is referred to as "build coordination".

Periodic builds (those which are run every N seconds rather than after new Changes arrive) are triggered by a special :bb:sched:`Periodic` scheduler.

Each scheduler creates and submits :class:`BuildSet` objects to the :class:`BuildMaster`, which is then responsible for making sure the individual :class:`BuildRequests` are delivered to the target :class:`Builder`\s.

Scheduler instances are activated by placing them in the :bb:cfg:`schedulers` list in the buildmaster config file.
Each scheduler must have a unique name.

.. _BuildSet:

BuildSets
---------

A :class:`BuildSet` is the name given to a set of :class:`Build`\s that all compile/test the same version of the tree on multiple :class:`Builder`\s.
In general, all these component :class:`Build`\s will perform the same sequence of :class:`Step`\s, using the same source code, but on different platforms or against a different set of libraries.

The :class:`BuildSet` is tracked as a single unit, which fails if any of the component :class:`Build`\s have failed, and therefore can succeed only if *all* of the component :class:`Build`\s have succeeded.
There are two kinds of status notification messages that can be emitted for a :class:`BuildSet`: the ``firstFailure`` type (which fires as soon as we know the :class:`BuildSet` will fail), and the ``Finished`` type (which fires once the :class:`BuildSet` has completely finished, regardless of whether the overall set passed or failed).

A :class:`BuildSet` is created with set of one or more *source stamp* tuples of ``(branch, revision, changes, patch)``, some of which may be ``None``, and a list of :class:`Builder`\s on which it is to be run.
They are then given to the BuildMaster, which is responsible for creating a separate :class:`BuildRequest` for each :class:`Builder`.

There are a couple of different likely values for the ``SourceStamp``:

:samp:`(revision=None, changes={CHANGES}, patch=None)`
    This is a :class:`SourceStamp` used when a series of :class:`Change`\s have triggered a build.
    The VC step will attempt to check out a tree that contains *CHANGES* (and any changes that occurred before *CHANGES*, but not any that occurred after them.)

:samp:`(revision=None, changes=None, patch=None)`
    This builds the most recent code on the default branch.
    This is the sort of :class:`SourceStamp` that would be used on a :class:`Build` that was triggered by a user request, or a :bb:sched:`Periodic` scheduler.
    It is also possible to configure the VC Source Step to always check out the latest sources rather than paying attention to the :class:`Change`\s in the :class:`SourceStamp`, which will result in same behavior as this.

:samp:`(branch={BRANCH}, revision=None, changes=None, patch=None)`
    This builds the most recent code on the given *BRANCH*.
    Again, this is generally triggered by a user request or a :bb:sched:`Periodic` scheduler.

:samp:`(revision={REV}, changes=None, patch=({LEVEL}, {DIFF}, {SUBDIR_ROOT}))`
    This checks out the tree at the given revision *REV*, then applies a patch (using ``patch -pLEVEL <DIFF``) from inside the relative directory *SUBDIR_ROOT*.
    Item *SUBDIR_ROOT* is optional and defaults to the builder working directory.
    The :bb:cmdline:`try` command creates this kind of :class:`SourceStamp`.
    If ``patch`` is ``None``, the patching step is bypassed.

The buildmaster is responsible for turning the :class:`BuildSet` into a set of :class:`BuildRequest` objects and queueing them on the appropriate :class:`Builder`\s.

.. _BuildRequest:

BuildRequests
-------------

A :class:`BuildRequest` is a request to build a specific set of source code (specified by one or more source stamps) on a single :class:`Builder`.
Each :class:`Builder` runs the :class:`BuildRequest` as soon as it can (i.e. when an associated worker becomes free).
:class:`BuildRequest`\s are prioritized from oldest to newest, so when a worker becomes free, the :class:`Builder` with the oldest :class:`BuildRequest` is run.

The :class:`BuildRequest` contains one :class:`SourceStamp` specification per codebase.
The actual process of running the build (the series of :class:`Step`\s that will be executed) is implemented by the :class:`Build` object.
In the future this might be changed, to have the :class:`Build` define *what* gets built, and a separate :class:`BuildProcess` (provided by the Builder) to define *how* it gets built.

The :class:`BuildRequest` may be mergeable with other compatible :class:`BuildRequest`\s.
Builds that are triggered by incoming :class:`Change`\s will generally be mergeable.
Builds that are triggered by user requests are generally not, unless they are multiple requests to build the *latest sources* of the same branch.
A merge of buildrequests is performed per codebase, thus on changes having the same codebase.

.. _Builder:

Builders
--------

A :class:`Builder` handles the process of scheduling work to workers.
Each :class:`Builder` is responsible for a certain type of build, which usually consist of identical or very similar sequence of steps.

The class serves as a kind of queue for that particular type of build.
In general, each :class:`Builder` runs independently, but it's possible to constrain the behavior of :class:`Builder`\s using various kinds of interlocks.

Each builder is a long-lived object which controls a sequence of :class:`Build`\s.
A :class:`Builder` is created when the config file is first parsed, and lives forever (or rather until it is removed from the config file).
It mediates the connections to the workers that do all the work, and is responsible for creating the :class:`Build` objects - :ref:`Concepts-Build`.

Each builder gets a unique name, and the path name of a directory where it gets to do all its work.
This path is used in two ways.
On the buildmaster-side a directory is created for keeping status information.
On the worker-side a directory is created where the actual checkout, compile and test commands are executed.

.. _Concepts-Build-Factories:

Build Factories
---------------

A builder also has a :class:`BuildFactory`, which is responsible for creating new :class:`Build` instances: because the :class:`Build` instance is what actually performs each build, choosing the :class:`BuildFactory` is the way to specify what happens each time a build is done (:ref:`Concepts-Build`).

.. _Concepts-Workers:

Workers
-------

A :class:`Worker`\s corresponds to an environment where builds are executed.
A single physical machine must run at least one :class:`Worker`\s in order for Buildbot to be able to utilize it for running builds.
Multiple :class:`Worker`\s may run on a single machine to provide different environments that can reuse the same hardware by means of containers or virtual machines.

Each builder is associated with one or more :class:`Worker`\s.
For example, a builder which is used to perform macOS builds (as opposed to Linux or Windows builds) should naturally be associated with a Mac worker.

If multiple workers are available for any given builder, you will have some measure of redundancy: in case one worker goes offline, the others can still keep the :class:`Builder` working.
In addition, multiple workers will allow multiple simultaneous builds for the same :class:`Builder`, which might be useful if you have a lot of forced or ``try`` builds taking place.

Ideally, each :class:`Worker` that is configured for a builder should be identical.
Otherwise build or test failures will be dependent on which worker the build is ran and this will complicate investigation of failures.

.. _Concepts-Build:

Builds
------

A :class:`Build` is a single compile or test run of a particular version of the source code, and is comprised of a series of steps.
The steps may be arbitrary. For example, for compiled software a build generally consists of the checkout, configure, make, and make check sequence.
For interpreted projects like Python modules, a build is generally a checkout followed by an invocation of the bundled test suite.

A :class:`BuildFactory` describes the steps a build will perform.
The builder which starts a build uses its configured build factory to determine the build's steps.

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
When a Change is first rendered, the ``who`` attribute is parsed and added to the database if it doesn't exist or checked against an existing user.
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
The password will be encrypted before storing in the database along with other user attributes.

.. _Doing-Things-With-Users:

Doing Things With Users
~~~~~~~~~~~~~~~~~~~~~~~

Each change has a single user who is responsible for it.
Most builds have a set of changes: the build generally represents the first time these changes have been built and tested by the Buildbot.
The build has a *blamelist* that is the union of the users responsible for all the build's changes.
If the build was created by a :ref:`Try-Schedulers` this list will include the submitter of the try job, if known.

The build provides a list of users who are interested in the build -- the *interested users*.
Usually this is equal to the blamelist, but may also be expanded, e.g., to include the current build sherrif or a module's maintainer.

If desired, the buildbot can notify the interested users until the problem is resolved.

.. _Email-Addresses:

Email Addresses
~~~~~~~~~~~~~~~

The :bb:reporter:`MailNotifier` is a status target which can send email about the results of each build.
It accepts a static list of email addresses to which each message should be delivered, but it can also be configured to send mail to the :class:`Build`\'s Interested Users.
To do this, it needs a way to convert User names into email addresses.

For many VC systems, the User Name is actually an account name on the system which hosts the repository.
As such, turning the name into an email address is a simple matter of appending ``@repositoryhost.com``.
Some projects use other kinds of mappings (for example the preferred email address may be at ``project.org`` despite the repository host being named ``cvs.project.org``), and some VC systems have full separation between the concept of a user and that of an account on the repository host (like Perforce).
Some systems (like Git) put a full contact email address in every change.

To convert these names to addresses, the :class:`MailNotifier` uses an :class:`EmailLookup` object.
This provides a :meth:`getAddress` method which accepts a name and (eventually) returns an address.
The default :class:`MailNotifier` module provides an :class:`EmailLookup` which simply appends a static string, configurable when the notifier is created.
To create more complex behaviors (perhaps using an LDAP lookup, or using ``finger`` on a central host to determine a preferred address for the developer), provide a different object as the ``lookup`` argument.

If an EmailLookup object isn't given to the MailNotifier, the MailNotifier will try to find emails through :ref:`User-Objects`.
This will work the same as if an EmailLookup object was used if every user in the Build's Interested Users list has an email in the database for them.
If a user whose change led to a Build doesn't have an email attribute, that user will not receive an email.
If ``extraRecipients`` is given, those users are still sent mail when the EmailLookup object is not specified.

In the future, when the Problem mechanism has been set up, the Buildbot will need to send mail to arbitrary Users.
It will do this by locating a :class:`MailNotifier`\-like object among all the buildmaster's status targets, and asking it to send messages to various Users.
This means the User-to-address mapping only has to be set up once, in your :class:`MailNotifier`, and every email message the buildbot emits will take advantage of it.

.. _IRC-Nicknames:

IRC Nicknames
~~~~~~~~~~~~~

Like :class:`MailNotifier`, the :class:`buildbot.status.words.IRC` class provides a status target which can announce the results of each build.
It also provides an interactive interface by responding to online queries posted in the channel or sent as private messages.

In the future, the buildbot can be configured to map User names to IRC nicknames, to watch for the recent presence of these nicknames, and to deliver build status messages to the interested parties.
Like :class:`MailNotifier` does for email addresses, the :class:`IRC` object will have an :class:`IRCLookup` which is responsible for nicknames.
The mapping can be set up statically, or it can be updated by online users themselves (by claiming a username with some kind of ``buildbot: i am user warner`` commands).

Once the mapping is established, the rest of the buildbot can ask the :class:`IRC` object to send messages to various users.
It can report on the likelihood that the user saw the given message (based upon how long the user has been inactive on the channel), which might prompt the Problem Hassler logic to send them an email message instead.

These operations and authentication of commands issued by particular nicknames will be implemented in :ref:`User-Objects`.

.. index:: Properties

.. _Build-Properties:

Build Properties
----------------

Each build has a set of *Build Properties*, which can be used by its build steps to modify their actions.
These properties, in the form of key-value pairs, provide a general framework for dynamically altering the behavior of a build based on its circumstances.

Properties form a simple kind of variable in a build.
Some properties are set when the build starts, and properties can be changed as a build progresses -- properties set or changed in one step may be accessed in subsequent steps.
Property values can be numbers, strings, lists, or dictionaries - basically, anything that can be represented in JSON.

Properties are very flexible, and can be used to implement all manner of functionality.
Here are some examples:

Most Source steps record the revision that they checked out in the ``got_revision`` property.
A later step could use this property to specify the name of a fully-built tarball, dropped in an easily-accessible directory for later testing.

.. note::

   In builds with more than one codebase, the ``got_revision`` property is a dictionary, keyed by codebase.

Some projects want to perform nightly builds as well as building in response to committed changes.
Such a project would run two schedulers, both pointing to the same set of builders, but could provide an ``is_nightly`` property so that steps can distinguish the nightly builds, perhaps to run more resource-intensive tests.

Some projects have different build processes on different systems.
Rather than create a build factory for each worker, the steps can use worker properties to identify the unique aspects of each worker and adapt the build process dynamically.

.. _Multiple-Codebase-Builds:

Multiple-Codebase Builds
------------------------

What if an end-product is composed of code from several codebases?
Changes may arrive from different repositories within the tree-stable-timer period.
Buildbot will not only use the source-trees that contain changes but also needs the remaining source-trees to build the complete product.

For this reason a :ref:`Scheduler<Scheduling-Builds>` can be configured to base a build on a set of several source-trees that can (partly) be overridden by the information from incoming :class:`Change`\s.

As described :ref:`above <Source-Stamps>`, the source for each codebase is identified by a source stamp, containing its repository, branch and revision.
A full build set will specify a source stamp set describing the source to use for each codebase.

Configuring all of this takes a coordinated approach.  A complete multiple repository configuration consists of:

a *codebase generator*

    Every relevant change arriving from a VC must contain a codebase.
    This is done by a :bb:cfg:`codebaseGenerator` that is defined in the configuration.
    Most generators examine the repository of a change to determine its codebase, using project-specific rules.

some *schedulers*

    Each :bb:cfg:`scheduler<schedulers>` has to be configured with a set of all required ``codebases`` to build a product.
    These codebases indicate the set of required source-trees.
    In order for the scheduler to be able to produce a complete set for each build, the configuration can give a default repository, branch, and revision for each codebase.
    When a scheduler must generate a source stamp for a codebase that has received no changes, it applies these default values.

multiple *source steps* - one for each codebase

    A :ref:`Builder`'s build factory must include a :ref:`source step<Source-Checkout>` for each codebase.
    Each of the source steps has a ``codebase`` attribute which is used to select an appropriate source stamp from the source stamp set for a build.
    This information comes from the arrived changes or from the scheduler's configured default values.

    .. note::

        Each :ref:`source step<Source-Checkout>` has to have its own ``workdir`` set in order for the checkout to be done for each codebase in its own directory.

    .. note::

        Ensure you specify the codebase within your source step's Interpolate() calls (ex. ``http://.../svn/%(src:codebase:branch)s)``.
        See :ref:`Interpolate` for details.

.. warning::

    Defining a :bb:cfg:`codebaseGenerator` that returns non-empty (not ``''``) codebases will change the behavior of all the schedulers.

.. _Multimaster:

Multimaster
-----------

.. Warning::

    Buildbot Multimaster is considered experimental.
    There are still some companies using it in production.
    Don't hesitate to use the mailing lists to share your experience.

.. blockdiag::

    blockdiag multimaster {
       Worker1 -> LoadBalancer -> Master1 -> database
       Worker2 -> LoadBalancer
       Worker2 [shape = "dots"];
       WorkerN -> LoadBalancer -> Master2 -> database
       User1 -> LoadBalancerUI -> MasterUI1 -> database
       User2 -> LoadBalancerUI -> MasterUI2 -> database
       Master1 -> crossbar.io
       Master2 -> crossbar.io
       MasterUI1 -> crossbar.io
       MasterUI2 -> crossbar.io
       database [shape = "flowchart.database", stacked];
       LoadBalancerUI [shape = ellipse];
       LoadBalancer [shape = ellipse];
       crossbar.io [shape = mail];
       User1 [shape = actor];
       User2 [shape = actor];
       default_shape = roundedbox;
       default_node_color = "#33b5e5";
       default_group_color = "#428bca";
       default_linecolor = "#0099CC";
       default_textcolor = "#e1f5fe";
       group {
          shape = line;
          Worker1; Worker2; WorkerN
       }
       group {
          shape = line;
          Master1; Master2; MasterUI1; MasterUI2
       }
       group {
          shape = line;
          database; crossbar.io;
       }
       group {
          shape = line;
          User1; User2;
       }
    }

Buildbot supports interconnection of several masters.
This has to be done through a multi-master enabled message queue backend.
As of now the only one supported is wamp and crossbar.io.
see :ref:`wamp <MQ-Specification>`

There are then several strategy for introducing multimaster in your buildbot infra.
A simple way to say it is by adding the concept of symmetrics and asymmetrics multimaster (like there is SMP and AMP for multi core CPUs)

Symmetric multimaster is when each master share the exact same configuration. They run the same builders, same schedulers, same everything, the only difference is that workers are connected evenly between the masters (by any means (e.g. DNS load balancing, etc)) Symmetric multimaster is good to use to scale buildbot horizontally.

Asymmetric multimaster is when each master have different configuration. Each master may have a specific responsibility (e.g schedulers, set of builder, UI). This was more how you did in 0.8, also because of its own technical limitations. A nice feature of asymmetric multimaster is that you can have the UI only handled by some masters.

Separating the UI from the controlling will greatly help in the performance of the UI, because badly written BuildSteps?? can stall the reactor for several seconds.

The fanciest configuration would probably be a symmetric configuration for everything but the UI.
You would scale the number of UI master according to your number of UI users, and scale the number of engine masters to the number of workers.

Depending on your workload and size of master host, it is probably a good idea to start thinking of multimaster starting from a hundred workers connected.

Multimaster can also be used for high availability, and seamless upgrade of configuration code.
Complex configuration indeed requires sometimes to restart the master to reload custom steps or code, or just to upgrade the upstream buildbot version.

In this case, you will implement following procedure:

* Start new master(s) with new code and configuration.
* Send a graceful shutdown to the old master(s).
* New master(s) will start taking the new jobs, while old master(s) will just finish managing the running builds.
* As an old master is finishing the running builds, it will drop the connections from the workers, who will then reconnect automatically, and by the mean of load balancer will get connected to a new master to run new jobs.

As buildbot nine has been designed to allow such procedure, it has not been implemented in production yet as we know.
There is probably a new REST api needed in order to graceful shutdown a master, and the details of gracefully dropping the connection to the workers to be sorted out.
