Concepts
========

This chapter defines some of the basic concepts that the Buildbot
uses. You'll need to understand how the Buildbot sees the world to
configure it properly.

.. _Version-Control-Systems:

Version Control Systems
-----------------------

These source trees come from a Version Control System of some kind.
CVS and Subversion are two popular ones, but the Buildbot supports
others. All VC systems have some notion of an upstream
`repository` which acts as a server [#]_, from which clients
can obtain source trees according to various parameters. The VC
repository provides source trees of various projects, for different
branches, and from various points in time. The first thing we have to
do is to specify which source tree we want to get.

.. _Generalizing-VC-Systems:

Generalizing VC Systems
~~~~~~~~~~~~~~~~~~~~~~~

For the purposes of the Buildbot, we will try to generalize all VC
systems as having repositories that each provide sources for a variety
of projects. Each project is defined as a directory tree with source
files. The individual files may each have revisions, but we ignore
that and treat the project as a whole as having a set of revisions
(CVS is the only VC system still in widespread use that has
per-file revisions, as everything modern has moved to atomic tree-wide
changesets). Each time someone commits a change to the project, a new
revision becomes available. These revisions can be described by a
tuple with two items: the first is a branch tag, and the second is
some kind of revision stamp or timestamp. Complex projects may have
multiple branch tags, but there is always a default branch. The
timestamp may be an actual timestamp (such as the :option:`-D` option to CVS),
or it may be a monotonically-increasing transaction number (such as
the change number used by SVN and P4, or the revision number used by
Bazaar, or a labeled tag used in CVS. [#]_)
The SHA1 revision ID used by Mercurial, and Git is
also a kind of revision stamp, in that it specifies a unique copy of
the source tree, as does a Darcs ``context`` file.

When we aren't intending to make any changes to the sources we check out
(at least not any that need to be committed back upstream), there are two
basic ways to use a VC system:

  * Retrieve a specific set of source revisions: some tag or key is used
    to index this set, which is fixed and cannot be changed by subsequent
    developers committing new changes to the tree. Releases are built from
    tagged revisions like this, so that they can be rebuilt again later
    (probably with controlled modifications).

  * Retrieve the latest sources along a specific branch: some tag is used
    to indicate which branch is to be used, but within that constraint we want
    to get the latest revisions.

Build personnel or CM staff typically use the first approach: the
build that results is (ideally) completely specified by the two
parameters given to the VC system: repository and revision tag. This
gives QA and end-users something concrete to point at when reporting
bugs. Release engineers are also reportedly fond of shipping code that
can be traced back to a concise revision tag of some sort.

Developers are more likely to use the second approach: each morning
the developer does an update to pull in the changes committed by the
team over the last day. These builds are not easy to fully specify: it
depends upon exactly when you did a checkout, and upon what local
changes the developer has in their tree. Developers do not normally
tag each build they produce, because there is usually significant
overhead involved in creating these tags. Recreating the trees used by
one of these builds can be a challenge. Some VC systems may provide
implicit tags (like a revision number), while others may allow the use
of timestamps to mean "the state of the tree at time X" as opposed
to a tree-state that has been explicitly marked.

The Buildbot is designed to help developers, so it usually works in
terms of *the latest* sources as opposed to specific tagged
revisions. However, it would really prefer to build from reproducible
source trees, so implicit revisions are used whenever possible.

.. _Source-Tree-Specifications:

Source Tree Specifications
~~~~~~~~~~~~~~~~~~~~~~~~~~

So for the Buildbot's purposes we treat each VC system as a server
which can take a list of specifications as input and produce a source
tree as output. Some of these specifications are static: they are
attributes of the builder and do not change over time. Others are more
variable: each build will have a different value. The repository is
changed over time by a sequence of Changes, each of which represents a
single developer making changes to some set of files. These Changes
are cumulative.

For normal builds, the Buildbot wants to get well-defined source trees
that contain specific :class:`Change`\s, and exclude other :class:`Change`\s that may have
occurred after the desired ones. We assume that the :class:`Change`\s arrive at
the buildbot (through one of the mechanisms described in
:ref:`Change-Sources`) in the same order in which they are committed to the
repository. The Buildbot waits for the tree to become ``stable``
before initiating a build, for two reasons. The first is that
developers frequently make multiple related commits in quick
succession, even when the VC system provides ways to make atomic
transactions involving multiple files at the same time. Running a
build in the middle of these sets of changes would use an inconsistent
set of source files, and is likely to fail (and is certain to be less
useful than a build which uses the full set of changes). The
tree-stable-timer is intended to avoid these useless builds that
include some of the developer's changes but not all. The second reason
is that some VC systems (i.e. CVS) do not provide repository-wide
transaction numbers, so that timestamps are the only way to refer to
a specific repository state. These timestamps may be somewhat
ambiguous, due to processing and notification delays. By waiting until
the tree has been stable for, say, 10 minutes, we can choose a
timestamp from the middle of that period to use for our source
checkout, and then be reasonably sure that any clock-skew errors will
not cause the build to be performed on an inconsistent set of source
files.

The :class:`Scheduler`\s always use the tree-stable-timer, with a timeout that
is configured to reflect a reasonable tradeoff between build latency
and change frequency. When the VC system provides coherent
repository-wide revision markers (such as Subversion's revision
numbers, or in fact anything other than CVS's timestamps), the
resulting :class:`Build` is simply performed against a source tree defined by
that revision marker. When the VC system does not provide this, a
timestamp from the middle of the tree-stable period is used to
generate the source tree [#]_.

.. _How-Different-VC-Systems-Specify-Sources:

How Different VC Systems Specify Sources
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

For CVS, the static specifications are *repository* and
*module*. In addition to those, each build uses a timestamp (or
omits the timestamp to mean *the latest*) and *branch tag*
(which defaults to ``HEAD``). These parameters collectively specify a set
of sources from which a build may be performed.

`Subversion <http://subversion.tigris.org>`_,  combines the
repository, module, and branch into a single *Subversion URL*
parameter. Within that scope, source checkouts can be specified by a
numeric *revision number* (a repository-wide
monotonically-increasing marker, such that each transaction that
changes the repository is indexed by a different revision number), or
a revision timestamp. When branches are used, the repository and
module form a static ``baseURL``, while each build has a
*revision number* and a *branch* (which defaults to a
statically-specified ``defaultBranch``). The ``baseURL`` and
``branch`` are simply concatenated together to derive the
``svnurl`` to use for the checkout.

`Perforce <http://www.perforce.com/>`_ is similar. The server
is specified through a ``P4PORT`` parameter. Module and branch
are specified in a single depot path, and revisions are
depot-wide. When branches are used, the ``p4base`` and
``defaultBranch`` are concatenated together to produce the depot
path.


`Bzr <http://bazaar-vcs.org>`_ (which is a descendant of
Arch/Bazaar, and is frequently referred to as "Bazaar") has the same
sort of repository-vs-workspace model as Arch, but the repository data
can either be stored inside the working directory or kept elsewhere
(either on the same machine or on an entirely different machine). For
the purposes of Buildbot (which never commits changes), the repository
is specified with a URL and a revision number.

The most common way to obtain read-only access to a bzr tree is via
HTTP, simply by making the repository visible through a web server
like Apache. Bzr can also use FTP and SFTP servers, if the buildslave
process has sufficient privileges to access them. Higher performance
can be obtained by running a special Bazaar-specific server. None of
these matter to the buildbot: the repository URL just has to match the
kind of server being used. The ``repoURL`` argument provides the
location of the repository.

Branches are expressed as subdirectories of the main central
repository, which means that if branches are being used, the BZR step
is given a ``baseURL`` and ``defaultBranch`` instead of getting
the ``repoURL`` argument.


`Darcs <http://darcs.net/>`_ doesn't really have the
notion of a single master repository. Nor does it really have
branches. In Darcs, each working directory is also a repository, and
there are operations to push and pull patches from one of these
``repositories`` to another. For the Buildbot's purposes, all you
need to do is specify the URL of a repository that you want to build
from. The build slave will then pull the latest patches from that
repository and build them. Multiple branches are implemented by using
multiple repositories (possibly living on the same server).

Builders which use Darcs therefore have a static ``repourl`` which
specifies the location of the repository. If branches are being used,
the source Step is instead configured with a ``baseURL`` and a
``defaultBranch``, and the two strings are simply concatenated
together to obtain the repository's URL. Each build then has a
specific branch which replaces ``defaultBranch``, or just uses the
default one. Instead of a revision number, each build can have a
``context``, which is a string that records all the patches that are
present in a given tree (this is the output of ``darcs changes
--context``, and is considerably less concise than, e.g. Subversion's
revision number, but the patch-reordering flexibility of Darcs makes
it impossible to provide a shorter useful specification).


`Mercurial <http://selenic.com/mercurial>`_ is like Darcs, in that
each branch is stored in a separate repository. The ``repourl``,
``baseURL``, and ``defaultBranch`` arguments are all handled the
same way as with Darcs. The *revision*, however, is the hash
identifier returned by ``hg identify``.


`Git <http://git.or.cz/>`_ also follows a decentralized model, and
each repository can have several branches and tags. The source Step is
configured with a static ``repourl`` which specifies the location
of the repository. In addition, an optional ``branch`` parameter
can be specified to check out code from a specific branch instead of
the default *master* branch. The *revision* is specified as a SHA1
hash as returned by e.g. ``git rev-parse``. No attempt is made
to ensure that the specified revision is actually a subset of the
specified branch.

`Monotone <http://www.monotone.ca/>`_ is another that follows a
decentralized model where each repository can have several branches and
tags. The source Step is configured with static ``repourl`` and
``branch`` parameters, which specifies the location of the
repository and the branch to use.  The *revision* is specified as a
SHA1 hash as returned by e.g. ``mtn automate select w:``. No
attempt is made to ensure that the specified revision is actually a
subset of the specified branch.

.. _Attributes-of-Changes:

Attributes of Changes
~~~~~~~~~~~~~~~~~~~~~

.. _Attr-Who:

Who
+++

Each :class:`Change` has a :attr:`who` attribute, which specifies which developer is
responsible for the change. This is a string which comes from a namespace
controlled by the VC repository. Frequently this means it is a username on the
host which runs the repository, but not all VC systems require this.  Each
:class:`StatusNotifier` will map the :attr:`who` attribute into something appropriate for
their particular means of communication: an email address, an IRC handle, etc.

This ``who`` attribute is also parsed and stored into Buildbot's database (see
:ref:`User-Objects`). Currently, only ``who`` attributes in Changes from
``git`` repositories are translated into user objects, but in the future all
incoming Changes will have their ``who`` parsed and stored.

.. _Attr-Files:

Files
+++++

It also has a list of :attr:`files`, which are just the tree-relative
filenames of any files that were added, deleted, or modified for this
:class:`Change`. These filenames are used by the :func:`fileIsImportant`
function (in the :class:`Scheduler`) to decide whether it is worth triggering a
new build or not, e.g. the function could use the following function
to only run a build if a C file were checked in::

    def has_C_files(change):
        for name in change.files:
            if name.endswith(".c"):
                return True
        return False

Certain :class:`BuildStep`\s can also use the list of changed files
to run a more targeted series of tests, e.g. the
``python_twisted.Trial`` step can run just the unit tests that
provide coverage for the modified .py files instead of running the
full test suite.

.. _Attr-Comments:

Comments
++++++++

The Change also has a :attr:`comments` attribute, which is a string
containing any checkin comments.

.. _Attr-Project:

Project
+++++++

A change's :attr:`project`, by default the empty string, describes the source code
that changed.  It is a free-form string which the buildbot administrator can
use to flexibly discriminate among changes.

Generally, a project is an independently-buildable unit of source.  This field
can be used to apply different build steps to different projects.  For example,
an open-source application might build its Windows client from a separate
codebase than its POSIX server.  In this case, the change sources should be
configured to attach an appropriate project string (say, "win-client" and
"server") to changes from each codebase.  Schedulers would then examine these
strings and trigger the appropriate builders for each project.

.. _Attr-Repository:

Repository
++++++++++

A change occurs within the context of a specific repository.  This is generally
specified with a string, and for most version-control systems, this string
takes the form of a URL.

:class:`Change`\s can be filtered on repository, but more often this field is used as a
hint for the build steps to figure out which code to check out.

.. _Attr-Revision:

Revision
++++++++

Each Change can have a :attr:`revision` attribute, which describes how
to get a tree with a specific state: a tree which includes this Change
(and all that came before it) but none that come after it. If this
information is unavailable, the :attr:`revision` attribute will be
``None``. These revisions are provided by the :class:`ChangeSource`, and
consumed by the :meth:`computeSourceRevision` method in the appropriate
:class:`source.Source` class.

`CVS`
    :attr:`revision` is an int, seconds since the epoch
   
`SVN`
    :attr:`revision` is an int, the changeset number (r%d)
    
`Darcs`
    :attr:`revision` is a large string, the output of :command:`darcs changes --context`

`Mercurial`
    :attr:`revision` is a short string (a hash ID), the output of :command:`hg identify`

`P4`
    :attr:`revision` is an int, the transaction number
    
`Git`
    :attr:`revision` is a short string (a SHA1 hash), the output of e.g.
    :command:`git rev-parse`


Branches
########

The Change might also have a :attr:`branch` attribute. This indicates
that all of the Change's files are in the same named branch. The
Schedulers get to decide whether the branch should be built or not.

For VC systems like CVS,  Git and Monotone the :attr:`branch`
name is unrelated to the filename. (that is, the branch name and the
filename inhabit unrelated namespaces). For SVN, branches are
expressed as subdirectories of the repository, so the file's
``svnurl`` is a combination of some base URL, the branch name, and the
filename within the branch. (In a sense, the branch name and the
filename inhabit the same namespace). Darcs branches are
subdirectories of a base URL just like SVN. Mercurial branches are the
same as Darcs.

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

Build Properties
################

A Change may have one or more properties attached to it, usually specified
through the Force Build form or :ref:`sendchange`. Properties are discussed
in detail in the :ref:`Build-Properties` section.

Links
#####

.. TODO: who is using 'links'? how is it being used?

Finally, the Change might have a :attr:`links` list, which is intended
to provide a list of URLs to a *viewcvs*-style web page that
provides more detail for this Change, perhaps including the full file
diffs.

.. _Scheduling-Builds:

Scheduling Builds
-----------------

Each Buildmaster has a set of :class:`Scheduler` objects, each of which
gets a copy of every incoming :class:`Change`. The Schedulers are responsible
for deciding when :class:`Build`\s should be run. Some Buildbot installations
might have a single :class:`Scheduler`, while others may have several, each for
a different purpose.

For example, a *quick* scheduler might exist to give immediate
feedback to developers, hoping to catch obvious problems in the code
that can be detected quickly. These typically do not run the full test
suite, nor do they run on a wide variety of platforms. They also
usually do a VC update rather than performing a brand-new checkout
each time.

A separate *full* scheduler might run more comprehensive tests, to
catch more subtle problems. configured to run after the quick scheduler, to give
developers time to commit fixes to bugs caught by the quick scheduler before
running the comprehensive tests.  This scheduler would also feed multiple
:class:`Builder`\s.


Many schedulers can be configured to wait a while after seeing a source-code
change - this is the *tree stable timer*.  The timer allows multiple commits to
be "batched" together.  This is particularly useful in distributed version
control systems, where a developer may push a long sequence of changes all at
once.  To save resources, it's often desirable only to test the most recent
change. 

Schedulers can also filter out the changes they are interested in, based on a
number of criteria.  For example, a scheduler that only builds documentation
might skip any changes that do not affect the documentation.  Schedulers can
also filter on the branch to which a commit was made.

There is some support for configuring dependencies between builds - for
example, you may want to build packages only for revisions which pass all of
the unit tests.  This support is under active development in Buildbot, and is
referred to as "build coordination".

Periodic builds (those which are run every N seconds rather than after
new Changes arrive) are triggered by a special :class:`Periodic`
Scheduler subclass. 

Each Scheduler creates and submits :class:`BuildSet` objects to the
:class:`BuildMaster`, which is then responsible for making sure the
individual :class:`BuildRequests` are delivered to the target
:class:`Builder`\s.

:class:`Scheduler` instances are activated by placing them in the
``c['schedulers']`` list in the buildmaster config file. Each
:class:`Scheduler` has a unique name.

.. _BuildSet:

BuildSet
--------

A :class:`BuildSet` is the name given to a set of :class:`Build`\s that all
compile/test the same version of the tree on multiple :class:`Builder`\s. In
general, all these component :class:`Build`\s will perform the same sequence of
:class:`Step`\s, using the same source code, but on different platforms or
against a different set of libraries.

The :class:`BuildSet` is tracked as a single unit, which fails if any of
the component :class:`Build`\s have failed, and therefore can succeed only if
*all* of the component :class:`Build`\s have succeeded. There are two kinds
of status notification messages that can be emitted for a :class:`BuildSet`:
the ``firstFailure`` type (which fires as soon as we know the
:class:`BuildSet` will fail), and the ``Finished`` type (which fires once
the :class:`BuildSet` has completely finished, regardless of whether the
overall set passed or failed).

A :class:`BuildSet` is created with a *source stamp* tuple of
``(branch, revision, changes, patch)``, some of which may be ``None``, and a
list of :class:`Builder`\s on which it is to be run. They are then given to the
BuildMaster, which is responsible for creating a separate
:class:`BuildRequest` for each :class:`Builder`.

There are a couple of different likely values for the
``SourceStamp``:

:samp:`(revision=None, changes={CHANGES}, patch=None)`
    This is a :class:`SourceStamp` used when a series of :class:`Change`\s have
    triggered a build. The VC step will attempt to check out a tree that
    contains *CHANGES* (and any changes that occurred before *CHANGES*, but
    not any that occurred after them.)

:samp:`(revision=None, changes=None, patch=None)`
    This builds the most recent code on the default branch. This is the
    sort of :class:`SourceStamp` that would be used on a :class:`Build` that was
    triggered by a user request, or a :class:`Periodic` scheduler. It is also
    possible to configure the VC Source Step to always check out the
    latest sources rather than paying attention to the :class:`Change`\s in the
    :class:`SourceStamp`, which will result in same behavior as this.

:samp:`(branch={BRANCH}, revision=None, changes=None, patch=None)`
    This builds the most recent code on the given *BRANCH*. Again, this is
    generally triggered by a user request or :class:`Periodic` build.

:samp:`(revision={REV}, changes=None, patch=({LEVEL}, {DIFF}, {SUBDIR_ROOT}))`
    This checks out the tree at the given revision *REV*, then applies a
    patch (using ``patch -pLEVEL <DIFF``) from inside the relative
    directory *SUBDIR_ROOT*. Item *SUBDIR_ROOT* is optional and defaults to the
    builder working directory. The :ref:`try` feature uses this kind of
    :class:`SourceStamp`. If ``patch`` is ``None``, the patching step is
    bypassed.

The buildmaster is responsible for turning the :class:`BuildSet` into a
set of :class:`BuildRequest` objects and queueing them on the
appropriate :class:`Builder`\s.

.. _BuildRequest:

BuildRequest
------------

A :class:`BuildRequest` is a request to build a specific set of source
code (spcified by a source stamp) on a single :class:`Builder`. Each :class:`Builder` runs the
:class:`BuildRequest` as soon as it can (i.e. when an associated
buildslave becomes free). :class:`BuildRequest`\s are prioritized from
oldest to newest, so when a buildslave becomes free, the
:class:`Builder` with the oldest :class:`BuildRequest` is run.

The :class:`BuildRequest` contains the :class:`SourceStamp` specification.
The actual process of running the build (the series of :class:`Step`\s that will
be executed) is implemented by the :class:`Build` object. In this future
this might be changed, to have the :class:`Build` define *what*
gets built, and a separate :class:`BuildProcess` (provided by the
Builder) to define *how* it gets built.

The :class:`BuildRequest` may be mergeable with other compatible
:class:`BuildRequest`\s. Builds that are triggered by incoming :class:`Change`\s
will generally be mergeable. Builds that are triggered by user
requests are generally not, unless they are multiple requests to build
the *latest sources* of the same branch.

.. _Builder:

Builder
-------

The Buildmaster runs a collection of :class:`Builder`\s, each of which handles a single
type of build (e.g. full versus quick), on one or more build slaves.   :class:`Builder`\s
serve as a kind of queue for a particular type of build.  Each :class:`Builder` gets a
separate column in the waterfall display. In general, each :class:`Builder` runs
independently (although various kinds of interlocks can cause one :class:`Builder` to
have an effect on another).

Each builder is a long-lived object which controls a sequence of :class:`Build`\s.
Each :class:`Builder` is created when the config file is first parsed, and lives forever
(or rather until it is removed from the config file). It mediates the
connections to the buildslaves that do all the work, and is responsible for
creating the :class:`Build` objects - :ref:`Concepts-Build`.

Each builder gets a unique name, and the path name of a directory where it gets
to do all its work (there is a buildmaster-side directory for keeping status
information, as well as a buildslave-side directory where the actual
checkout/compile/test commands are executed).

.. _Concepts-Build-Factories:

Build Factories
~~~~~~~~~~~~~~~

A builder also has a :class:`BuildFactory`, which is responsible for creating new :class:`Build`
instances: because the :class:`Build` instance is what actually performs each build,
choosing the :class:`BuildFactory` is the way to specify what happens each time a build
is done (:ref:`Concepts-Build`).

.. _Concepts-Build-Slaves:

Build Slaves
~~~~~~~~~~~~

Each builder is associated with one of more :class:`BuildSlave`\s.  A builder which is
used to perform Mac OS X builds (as opposed to Linux or Solaris builds) should
naturally be associated with a Mac buildslave.

If multiple buildslaves are available for any given builder, you will
have some measure of redundancy: in case one slave goes offline, the
others can still keep the :class:`Builder` working. In addition, multiple
buildslaves will allow multiple simultaneous builds for the same
:class:`Builder`, which might be useful if you have a lot of forced or ``try``
builds taking place.

If you use this feature, it is important to make sure that the
buildslaves are all, in fact, capable of running the given build. The
slave hosts should be configured similarly, otherwise you will spend a
lot of time trying (unsuccessfully) to reproduce a failure that only
occurs on some of the buildslaves and not the others. Different
platforms, operating systems, versions of major programs or libraries,
all these things mean you should use separate Builders.

.. _Concepts-Build:

Build
-----

A build is a single compile or test run of a particular version of the source
code, and is comprised of a series of steps.  It is ultimately up to you what
constitutes a build, but for compiled software it is generally the checkout,
configure, make, and make check sequence.  For interpreted projects like Python
modules, a build is generally a checkout followed by an invocation of the
bundled test suite.

A :class:`BuildFactory` describes the steps a build will perform.  The builder which
starts a build uses its configured build factory to determine the build's
steps.

.. _Concepts-Users:

Users
-----

Buildbot has a somewhat limited awareness of *users*. It assumes
the world consists of a set of developers, each of whom can be
described by a couple of simple attributes. These developers make
changes to the source code, causing builds which may succeed or fail.

Users also may have different levels of authorization when issuing Buildbot
commands, such as forcing a build from the web interface or from an IRC channel
(see :ref:`WebStatus-Configuration-Parameters` and :ref:`IRC-Bot`).

Each developer is primarily known through the source control system. Each
:class:`Change` object that arrives is tagged with a :attr:`who` field that
typically gives the account name (on the repository machine) of the user
responsible for that change. This string is displayed on the HTML status
pages and in each :class:`Build`\'s *blamelist*.

To do more with the User than just refer to them, this username needs to be
mapped into an address of some sort. The responsibility for this mapping is
left up to the status module which needs the address.  In the future, the
responsbility for managing users will be transferred to User Objects.

The ``who`` fields in ``git`` Changes are used to create :ref:`User-Objects`,
which allows for more control and flexibility in how Buildbot manages users.

.. _User-Objects:

User Objects
~~~~~~~~~~~~

User Objects allow Buildbot to better manage users throughout its various
interactions with users (see :ref:`Change-Sources` and :ref:`Status-Targets`).
The User Objects are stored in the Buildbot database and correlate the various
attributes that a user might have: irc, git, etc.

Changes
+++++++

Incoming Changes all have a ``who`` attribute attached to them that specifies
which developer is responsible for that Change. When a Change is first
rendered, the ``who`` attribute is parsed and added to the database if it
doesn't exist or checked against an existing user. The ``who`` attribute is
formatted in different ways depending on the version control system that the
Change came from.  Note that ``git`` is the only version control system
currently supported for User Object creation.

``git``
    ``who`` attributes take the form ``Full Name <Email>``.

Uses
++++

Correlating the various bits and pieces that Buildbot views as users also means
that one attribute of a user can be translated into another. This provides a
more complete view of users throughout Buildbot.

.. _Doing-Things-With-Users:

Doing Things With Users
~~~~~~~~~~~~~~~~~~~~~~~

Each change has a single user who is responsible for it. Most builds have a set
of changes: the build generally represents the first time these changes have
been built and tested by the Buildbot. The build has a *blamelist* that is
the union of the users responsible for all the build's changes. If the build
was created by a :ref:`Try-Schedulers` this list will include the submitter of the try
job, if known.

The build provides a list of users who are interested in the build -- the
*interested users*. Usually this is equal to the blamelist, but may also be
expanded, e.g., to include the current build sherrif or a module's maintainer.

If desired, the buildbot can notify the interested users until the problem is
resolved.  

.. _Email-Addresses:

Email Addresses
~~~~~~~~~~~~~~~

The :class:`buildbot.status.mail.MailNotifier` class
(:ref:`MailNotifier`) provides a status target which can send email
about the results of each build. It accepts a static list of email
addresses to which each message should be delivered, but it can also
be configured to send mail to the :class:`Build`\'s Interested Users. To do
this, it needs a way to convert User names into email addresses.

For many VC systems, the User Name is actually an account name on the
system which hosts the repository. As such, turning the name into an
email address is a simple matter of appending
``@repositoryhost.com``. Some projects use other kinds of mappings
(for example the preferred email address may be at ``project.org``
despite the repository host being named ``cvs.project.org``), and some
VC systems have full separation between the concept of a user and that
of an account on the repository host (like Perforce). Some systems
(like Git) put a full contact email address in every change.

To convert these names to addresses, the :class:`MailNotifier` uses an :class:`EmailLookup`
object. This provides a :meth:`getAddress` method which accepts a name and
(eventually) returns an address. The default :class:`MailNotifier`
module provides an :class:`EmailLookup` which simply appends a static string,
configurable when the notifier is created. To create more complex behaviors
(perhaps using an LDAP lookup, or using ``finger`` on a central host to
determine a preferred address for the developer), provide a different object
as the ``lookup`` argument.

In the future, when the Problem mechanism has been set up, the Buildbot
will need to send mail to arbitrary Users. It will do this by locating a
:class:`MailNotifier`\-like object among all the buildmaster's status targets, and
asking it to send messages to various Users. This means the User-to-address
mapping only has to be set up once, in your :class:`MailNotifier`, and every email
message the buildbot emits will take advantage of it.

.. _IRC-Nicknames:

IRC Nicknames
~~~~~~~~~~~~~

Like :class:`MailNotifier`, the :class:`buildbot.status.words.IRC` class
provides a status target which can announce the results of each build. It
also provides an interactive interface by responding to online queries
posted in the channel or sent as private messages.

In the future, the buildbot can be configured map User names to IRC
nicknames, to watch for the recent presence of these nicknames, and to
deliver build status messages to the interested parties. Like
:class:`MailNotifier` does for email addresses, the :class:`IRC` object
will have an :class:`IRCLookup` which is responsible for nicknames. The
mapping can be set up statically, or it can be updated by online users
themselves (by claiming a username with some kind of ``buildbot: i am
user warner`` commands).

Once the mapping is established, the rest of the buildbot can ask the
:class:`IRC` object to send messages to various users. It can report on
the likelihood that the user saw the given message (based upon how long the
user has been inactive on the channel), which might prompt the Problem
Hassler logic to send them an email message instead.

These operations and authentication of commands issued by particular
nicknames will be implemented in :ref:`User-Objects`.

.. _Live-Status-Clients:

Live Status Clients
~~~~~~~~~~~~~~~~~~~

The Buildbot also offers a desktop status client interface which can display
real-time build status in a GUI panel on the developer's desktop.

.. _Build-Properties:

Build Properties
----------------

Each build has a set of *Build Properties*, which can be used by its
:class:`BuildStep`\s to modify their actions.  These properties, in the form of
key-value pairs, provide a general framework for dynamically altering
the behavior of a build based on its circumstances.

Properties come from a number of places:

* global configuration -- These properties apply to all builds.
* schedulers -- A scheduler can specify properties available to all the builds it
  starts.
* changes -- A change can have properties attached to it. These are usually specified
  through a change source (:ref:`Change-Sources`), the "Force Build" form on
  the web interface (:ref:`WebStatus`), or sendchange (:ref:`sendchange`).
* buildslaves -- A buildslave can pass properties on to the builds it performs.
* builds -- A build automatically sets a number of properties on itself.
* builders -- A builder can set properties on all the builds it runs.
* steps -- The steps of a build can set properties that are available to subsequent
  steps.  In particular, source steps set a number of properties.

If the same property is supplied in multiple places, the final appearance takes
precedence.  For example, a property set in a builder configuration will
override one supplied by a scheduler.

Properties are very flexible, and can be used to implement all manner
of functionality.  Here are some examples:

Most Source steps record the revision that they checked out in
the ``got_revision`` property.  A later step could use this
property to specify the name of a fully-built tarball, dropped in an
easily-acessible directory for later testing.

Some projects want to perform nightly builds as well as bulding in response to
committed changes.  Such a project would run two schedulers, both pointing to
the same set of builders, but could provide an ``is_nightly`` property so
that steps can distinguish the nightly builds, perhaps to run more
resource-intensive tests.

Some projects have different build processes on different systems.
Rather than create a build factory for each slave, the steps can use
buildslave properties to identify the unique aspects of each slave
and adapt the build process dynamically.

.. rubric:: Footnotes

.. [#] Except Darcs, but since the Buildbot never modifies its local source tree we can ignore
    the fact that Darcs uses a less centralized model
    
.. [#] Many VC systems provide more complexity than this: in particular the local
    views that P4 and ClearCase can assemble out of various source
    directories are more complex than we're prepared to take advantage of
    here
    
.. [#] This ``checkoutDelay`` defaults
    to half the tree-stable timer, but it can be overridden with an
    argument to the :class:`Source` Step
