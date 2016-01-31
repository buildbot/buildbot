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

Source code comes from *repositories*, provided by version control systems.
Repositories are generally identified by URLs, e.g., ``git://github.com/buildbot/buildbot.git``.

In these days of distributed version control systems, the same *codebase* may appear in multiple repositories.
For example, ``https://github.com/mozilla/mozilla-central`` and ``http://hg.mozilla.org/mozilla-release`` both contain the Firefox codebase, although not exactly the same code.

Many *projects* are built from multiple codebases.
For example, a company may build several applications based on the same core library.
The "app" codebase and the "core" codebase are in separate repositories, but are compiled together and constitute a single project.
Changes to either codebase should cause a rebuild of the application.

Most version control systems define some sort of *revision* that can be used (sometimes in combination with a *branch*) to uniquely specify a particular version of the source code.

To build a project, Buildbot needs to know exactly which version of each codebase it should build.
It uses a *source stamp* to do so for each codebase; the collection of sourcestamps required for a project is called a *source stamp set*.

.. index: change

.. _Version-Control-Systems:

Version Control Systems
-----------------------

Buildbot supports a significant number of version control systems, so it treats them abstractly.

For purposes of deciding when to perform builds, Buildbot's change sources monitor repositories, and represent any updates to those repositories as *changes*.
These change sources fall broadly into two categories: pollers which periodically check the repository for updates; and hooks, where the repository is configured to notify Buildbot whenever an update occurs.

This concept does not map perfectly to every version control system.
For example, for CVS Buildbot must guess that version updates made to multiple files within a short time represent a single change; for DVCS's like Git, Buildbot records a change when a commit is pushed to the monitored repository, not when it is initially committed.
We assume that the :class:`Change`\s arrive at the master in the same order in which they are committed to the repository.

When it comes time to actually perform a build, a scheduler prepares a source stamp set, as described above, based on its configuration.
When the build begins, one or more source steps use the information in the source stamp set to actually check out the source code, using the normal VCS commands.

Tree Stability
~~~~~~~~~~~~~~

Changes tend to arrive at a buildmaster in bursts.
In many cases, these bursts of changes are meant to be taken together.
For example, a developer may have pushed multiple commits to a DVCS that comprise the same new feature or bugfix.
To avoid trying to build every change, Buildbot supports the notion of *tree stability*, by waiting for a burst of changes to finish before starting to schedule builds.
This is implemented as a timer, with builds not scheduled until no changes have occurred for the duration of the timer.

.. _How-Different-VC-Systems-Specify-Sources:

How Different VC Systems Specify Sources
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

For CVS, the static specifications are *repository* and *module*.
In addition to those, each build uses a timestamp (or omits the timestamp to mean *the latest*) and *branch tag* (which defaults to ``HEAD``).
These parameters collectively specify a set of sources from which a build may be performed.

`Subversion <http://subversion.tigris.org>`_,  combines the repository, module, and branch into a single *Subversion URL* parameter.
Within that scope, source checkouts can be specified by a numeric *revision number* (a repository-wide monotonically-increasing marker, such that each transaction that changes the repository is indexed by a different revision number), or a revision timestamp.
When branches are used, the repository and module form a static ``baseURL``, while each build has a *revision number* and a *branch* (which defaults to a statically-specified ``defaultBranch``).
The ``baseURL`` and ``branch`` are simply concatenated together to derive the ``repourl`` to use for the checkout.

`Perforce <http://www.perforce.com/>`_ is similar.
The server is specified through a ``P4PORT`` parameter.
Module and branch are specified in a single depot path, and revisions are depot-wide.
When branches are used, the ``p4base`` and ``defaultBranch`` are concatenated together to produce the depot path.

`Bzr <http://bazaar-vcs.org>`_ (which is a descendant of Arch/Bazaar, and is frequently referred to as "Bazaar") has the same sort of repository-vs-workspace model as Arch, but the repository data can either be stored inside the working directory or kept elsewhere (either on the same machine or on an entirely different machine).
For the purposes of Buildbot (which never commits changes), the repository is specified with a URL and a revision number.

The most common way to obtain read-only access to a bzr tree is via HTTP, simply by making the repository visible through a web server like Apache.
Bzr can also use FTP and SFTP servers, if the worker process has sufficient privileges to access them.
Higher performance can be obtained by running a special Bazaar-specific server.
None of these matter to the buildbot: the repository URL just has to match the kind of server being used.
The ``repoURL`` argument provides the location of the repository.

Branches are expressed as subdirectories of the main central repository, which means that if branches are being used, the BZR step is given a ``baseURL`` and ``defaultBranch`` instead of getting the ``repoURL`` argument.

`Darcs <http://darcs.net/>`_ doesn't really have the notion of a single master repository.
Nor does it really have branches.
In Darcs, each working directory is also a repository, and there are operations to push and pull patches from one of these ``repositories`` to another.
For the Buildbot's purposes, all you need to do is specify the URL of a repository that you want to build from.
The worker will then pull the latest patches from that repository and build them.
Multiple branches are implemented by using multiple repositories (possibly living on the same server).

Builders which use Darcs therefore have a static ``repourl`` which specifies the location of the repository.
If branches are being used, the source Step is instead configured with a ``baseURL`` and a ``defaultBranch``, and the two strings are simply concatenated together to obtain the repository's URL.
Each build then has a specific branch which replaces ``defaultBranch``, or just uses the default one.
Instead of a revision number, each build can have a ``context``, which is a string that records all the patches that are present in a given tree (this is the output of ``darcs changes --context``, and is considerably less concise than, e.g. Subversion's revision number, but the patch-reordering flexibility of Darcs makes it impossible to provide a shorter useful specification).

`Mercurial <http://selenic.com/mercurial>`_ is like Darcs, in that each branch is stored in a separate repository.
The ``repourl``, ``baseURL``, and ``defaultBranch`` arguments are all handled the same way as with Darcs.
The *revision*, however, is the hash identifier returned by ``hg identify``.

`Git <http://git.or.cz/>`_ also follows a decentralized model, and each repository can have several branches and tags.
The source Step is configured with a static ``repourl`` which specifies the location of the repository.
In addition, an optional ``branch`` parameter can be specified to check out code from a specific branch instead of the default *master* branch.
The *revision* is specified as a SHA1 hash as returned by e.g. ``git rev-parse``.
No attempt is made to ensure that the specified revision is actually a subset of the specified branch.

`Monotone <http://www.monotone.ca/>`_ is another that follows a decentralized model where each repository can have several branches and tags.
The source Step is configured with static ``repourl`` and ``branch`` parameters, which specifies the location of the repository and the branch to use.
The *revision* is specified as a SHA1 hash as returned by e.g. ``mtn automate select w:``.
No attempt is made to ensure that the specified revision is actually a subset of the specified branch.

.. index: change

.. _Attributes-of-Changes:

Changes
-------

.. _Attr-Who:

Who
~~~

Each :class:`Change` has a :attr:`who` attribute, which specifies which developer is responsible for the change.
This is a string which comes from a namespace controlled by the VC repository.
Frequently this means it is a username on the host which runs the repository, but not all VC systems require this.
Each :class:`StatusNotifier` will map the :attr:`who` attribute into something appropriate for their particular means of communication: an email address, an IRC handle, etc.

This ``who`` attribute is also parsed and stored into Buildbot's database (see :ref:`User-Objects`).
Currently, only ``who`` attributes in Changes from ``git`` repositories are translated into user objects, but in the future all incoming Changes will have their ``who`` parsed and stored.

.. _Attr-Files:

Files
~~~~~

It also has a list of :attr:`files`, which are just the tree-relative filenames of any files that were added, deleted, or modified for this :class:`Change`.
These filenames are used by the :func:`fileIsImportant` function (in the scheduler) to decide whether it is worth triggering a new build or not, e.g. the function could use the following function to only run a build if a C file were checked in::

    def has_C_files(change):
        for name in change.files:
            if name.endswith(".c"):
                return True
        return False

Certain :class:`BuildStep`\s can also use the list of changed files to run a more targeted series of tests, e.g. the ``python_twisted.Trial`` step can run just the unit tests that provide coverage for the modified .py files instead of running the full test suite.

.. _Attr-Comments:

Comments
~~~~~~~~

The Change also has a :attr:`comments` attribute, which is a string containing any checkin comments.

.. _Attr-Project:

Project
~~~~~~~

The :attr:`project` attribute of a change or source stamp describes the project to which it corresponds, as a short human-readable string.
This is useful in cases where multiple independent projects are built on the same buildmaster.
In such cases, it can be used to control which builds are scheduled for a given commit, and to limit status displays to only one project.

.. _Attr-Repository:

Repository
~~~~~~~~~~

This attribute specifies the repository in which this change occurred.
In the case of DVCS's, this information may be required to check out the committed source code.
However, using the repository from a change has security risks: if Buildbot is configured to blindly trust this information, then it may easily be tricked into building arbitrary source code, potentially compromising the workers and the integrity of subsequent builds.

.. _Attr-Codebase:

Codebase
~~~~~~~~

This attribute specifies the codebase to which this change was made.
As described :ref:`above <Source-Stamps>`, multiple repositories may contain the same codebase.
A change's codebase is usually determined by the :bb:cfg:`codebaseGenerator` configuration.
By default the codebase is ''; this value is used automatically for single-codebase configurations.

.. _Attr-Revision:

Revision
~~~~~~~~

Each Change can have a :attr:`revision` attribute, which describes how to get a tree with a specific state: a tree which includes this Change (and all that came before it) but none that come after it.
If this information is unavailable, the :attr:`revision` attribute will be ``None``.
These revisions are provided by the :class:`ChangeSource`.

Revisions are always strings.

`CVS`
    :attr:`revision` is the seconds since the epoch as an integer.

`SVN`
    :attr:`revision` is the revision number

`Darcs`
    :attr:`revision` is a large string, the output of :command:`darcs changes --context`

`Mercurial`
    :attr:`revision` is a short string (a hash ID), the output of :command:`hg identify`

`P4`
    :attr:`revision` is the transaction number

`Git`
    :attr:`revision` is a short string (a SHA1 hash), the output of e.g.  :command:`git rev-parse`

Branches
~~~~~~~~

The Change might also have a :attr:`branch` attribute.
This indicates that all of the Change's files are in the same named branch.
The schedulers get to decide whether the branch should be built or not.

For VC systems like CVS,  Git and Monotone the :attr:`branch` name is unrelated to the filename.
(That is, the branch name and the filename inhabit unrelated namespaces.)
For SVN, branches are expressed as subdirectories of the repository, so the file's ``repourl`` is a combination of some base URL, the branch name, and the filename within the branch.
(In a sense, the branch name and the filename inhabit the same namespace.)
Darcs branches are subdirectories of a base URL just like SVN.
Mercurial branches are the same as Darcs.

`CVS`
    branch='warner-newfeature', files=['src/foo.c']

`SVN`
    branch='branches/warner-newfeature', files=['src/foo.c']

`Darcs`
    branch='warner-newfeature', files=['src/foo.c']

`Mercurial`
    branch='warner-newfeature', files=['src/foo.c']

`Git`
    branch='warner-newfeature', files=['src/foo.c']

`Monotone`
    branch='warner-newfeature', files=['src/foo.c']

Change Properties
~~~~~~~~~~~~~~~~~

A Change may have one or more properties attached to it, usually specified through the Force Build form or :bb:cmdline:`sendchange`.
Properties are discussed in detail in the :ref:`Build-Properties` section.

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
configured to run after the quick scheduler, to give developers time to commit fixes to bugs caught by the quick scheduler before running the comprehensive tests.
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

A :class:`BuildRequest` is a request to build a specific set of source code (specified by one ore more source stamps) on a single :class:`Builder`.
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

The Buildmaster runs a collection of :class:`Builder`\s, each of which handles a single type of build (e.g. full versus quick), on one or more workers.
:class:`Builder`\s serve as a kind of queue for a particular type of build.
Each :class:`Builder` gets a separate column in the waterfall display.
In general, each :class:`Builder` runs independently (although various kinds of interlocks can cause one :class:`Builder` to have an effect on another).

Each builder is a long-lived object which controls a sequence of :class:`Build`\s.
Each :class:`Builder` is created when the config file is first parsed, and lives forever (or rather until it is removed from the config file).
It mediates the connections to the workers that do all the work, and is responsible for creating the :class:`Build` objects - :ref:`Concepts-Build`.

Each builder gets a unique name, and the path name of a directory where it gets to do all its work (there is a buildmaster-side directory for keeping status information, as well as a worker-side directory where the actual checkout/compile/test commands are executed).

.. _Concepts-Build-Factories:

Build Factories
---------------

A builder also has a :class:`BuildFactory`, which is responsible for creating new :class:`Build` instances: because the :class:`Build` instance is what actually performs each build, choosing the :class:`BuildFactory` is the way to specify what happens each time a build is done (:ref:`Concepts-Build`).

.. _Concepts-Workers:

Workers
-------

Each builder is associated with one of more :class:`Worker`\s.
A builder which is used to perform Mac OS X builds (as opposed to Linux or Solaris builds) should naturally be associated with a Mac worker.

If multiple workers are available for any given builder, you will have some measure of redundancy: in case one worker goes offline, the others can still keep the :class:`Builder` working.
In addition, multiple workers will allow multiple simultaneous builds for the same :class:`Builder`, which might be useful if you have a lot of forced or ``try`` builds taking place.

If you use this feature, it is important to make sure that the workers are all, in fact, capable of running the given build.
The worker hosts should be configured similarly, otherwise you will spend a lot of time trying (unsuccessfully) to reproduce a failure that only occurs on some of the workers and not the others.
Different platforms, operating systems, versions of major programs or libraries, all these things mean you should use separate Builders.

.. _Concepts-Build:

Builds
------

A build is a single compile or test run of a particular version of the source code, and is comprised of a series of steps.
It is ultimately up to you what constitutes a build, but for compiled software it is generally the checkout, configure, make, and make check sequence.
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

In the future, the buildbot can be configured map User names to IRC nicknames, to watch for the recent presence of these nicknames, and to deliver build status messages to the interested parties.
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
