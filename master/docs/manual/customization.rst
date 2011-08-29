.. _Customization:

Customization
=============

For advanced users, Buildbot acts as a framework supporting a customized build
framework.  For the most part, such configurations consist of subclasses set up
for use in a regular Buildbot configuration file.

This chapter describes some of the more common customizations made to Buildbot.
Future versions of Buildbot will ensure compatibility with the customizations
described here, and where that is not possible the changes will be announced in
the ``NEWS`` file.

.. _Merge-Request-Functions:

Merge Request Functions
-----------------------

.. index:: Builds; merging

The logic Buildbot uses to decide which build request can be merged can be
customized by providing a Python function (a callable) instead of ``True`` or
``False`` described in :ref:`Merging-Build-Requests`.

The callable will be invoked with three positional arguments: a
:class:`Builder` object and two :class:`BuildRequest` objects. It should return
true if the requests can be merged, and False otherwise. For example::

    def mergeRequests(builder, req1, req2):
        "any requests with the same branch can be merged"
        return req1.branch == req2.branch
    c['mergeRequests'] = mergeRequests

In many cases, the details of the :class:`SourceStamp`\s and :class:`BuildRequest`\s are important.
In this example, only :class:`BuildRequest`\s with the same "reason" are merged; thus
developers forcing builds for different reasons will see distinct builds.  Note
the use of the :func:`canBeMergedWith` method to access the source stamp
compatibility algorithm. ::

    def mergeRequests(builder, req1, req2):
        if req1.source.canBeMergedWith(req2.source) and  req1.reason == req2.reason:
           return True
        return False
    c['mergeRequests'] = mergeRequests

If it's necessary to perform some extended operation to determine whether two
requests can be merged, then the ``mergeRequests`` callable may return its
result via Deferred.  Note, however, that the number of invocations of the
callable is proportional to the square of the request queue length, so a
long-running callable may cause undesirable delays when the queue length
grows.  For example::

    def mergeRequests(builder, req1, req2):
        d = defer.gatherResults([
            getMergeInfo(req1.source.revision),
            getMergeInfo(req2.source.revision),
        ])
        def process(info1, info2):
            return info1 == info2
        d.addCallback(process)
        return d
    c['mergeRequests'] = mergeRequests

.. _Builder-Priority-Functions:

Builder Priority Functions
--------------------------

.. index:: Builders; priority

The :bb:cfg:`prioritizeBuilders` configuration key specifies a function which
is called with two arguments: a :class:`BuildMaster` and a list of
:class:`Builder` objects.  It should return a list of the same :class:`Builder`
objects, in the desired order.  It may also remove items from the list if
builds should not be started on those builders. If necessary, this function can
return its results via a Deferred (it is called with ``maybeDeferred``).

A simple ``prioritizeBuilders`` implementation might look like this::

    def prioritizeBuilders(buildmaster, builders):
        """Prioritize builders.  'finalRelease' builds have the highest
        priority, so they should be built before running tests, or
        creating builds."""
        builderPriorities = {
            "finalRelease": 0,
            "test": 1,
            "build": 2,
        }
        builders.sort(key=lambda b: builderPriorities.get(b.name, 0))
        return builders

    c['prioritizeBuilders'] = prioritizeBuilders

.. index:: Builds; priority

.. _Build-Priority-Functions:

Build Priority Functions
------------------------

When a builder has multiple pending build requests, it uses a ``nextBuild``
function to decide which build it should start first.  This function is given
two parameters: the :class:`Builder`, and a list of :class:`BuildRequest`
objects representing pending build requests.

A simple function to prioritize release builds over other builds might look
like this::

   def nextBuild(bldr, requests):
       for r in requests:
           if r.source.branch == 'release':
               return r
       return requests[0]

If some non-immediate result must be calculated, the ``nextBuild`` function can
also return a Deferred::

    def nextBuild(bldr, requests):
        d = get_request_priorities(requests)
        def pick(priorities):
            if requests:
                return sorted(zip(priorities, requests))[0][1]
        d.addCallback(pick)
        return d

.. _Customizing-SVNPoller:

Customizing SVNPoller
---------------------

Each source file that is tracked by a Subversion repository has a
fully-qualified SVN URL in the following form:
``({REPOURL})({PROJECT-plus-BRANCH})({FILEPATH})``. When you create the
:bb:chsrc:`SVNPoller`, you give it a ``svnurl`` value that includes all of the
``{REPOURL}`` and possibly some portion of the
``{PROJECT-plus-BRANCH}` string. The :bb:chsrc:`SVNPoller`` is responsible
for producing Changes that contain a branch name and a ``{FILEPATH}``
(which is relative to the top of a checked-out tree). The details of how these
strings are split up depend upon how your repository names its branches.

PROJECT/BRANCHNAME/FILEPATH repositories
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

One common layout is to have all the various projects that share a repository
get a single top-level directory each, with ``branches``, ``tags``, and
``trunk`` subdirectories:

.. code-block:: none

    amanda/trunk
          /branches/3_2
                   /3_3
          /tags/3_2_1
               /3_2_2
               /3_3_0

To set up a :bb:chsrc:`SVNPoller` that watches the Amanda trunk (and nothing
else), we would use the following, using the default ``split_file``::

    from buildbot.changes.svnpoller import SVNPoller
    c['change_source'] = SVNPoller(
       svnurl="https://svn.amanda.sourceforge.net/svnroot/amanda/amanda/trunk")

In this case, every Change that our :bb:chsrc:`SVNPoller` produces will have
its branch attribute set to ``None``, to indicate that the Change is on the
trunk.  No other sub-projects or branches will be tracked.

If we want our ChangeSource to follow multiple branches, we have to do
two things. First we have to change our ``svnurl=`` argument to
watch more than just ``amanda/trunk``. We will set it to
``amanda`` so that we'll see both the trunk and all the branches.
Second, we have to tell :bb:chsrc:`SVNPoller` how to split the
``({PROJECT-plus-BRANCH})({FILEPATH})`` strings it gets from the repository
out into ``({BRANCH})`` and ``({FILEPATH})``` pairs.

We do the latter by providing a ``split_file`` function. This function is
responsible for splitting something like ``branches/3_3/common-src/amanda.h``
into ``branch='branches/3_3'`` and ``filepath='common-src/amanda.h'``. The
function is always given a string that names a file relative to the
subdirectory pointed to by the :bb:chsrc:`SVNPoller`\'s ``svnurl=`` argument.
It is expected to return a ``({BRANCHNAME}, {FILEPATH})`` tuple (in which
``{FILEPATH}`` is relative to the branch indicated), or ``None`` to indicate
that the file is outside any project of interest.

.. note:: the function should return ``branches/3_3`` rather than just ``3_3``
    because the SVN checkout step, will append the branch name to the
    ``baseURL``, which requires that we keep the ``branches`` component in
    there. Other VC schemes use a different approach towards branches and may
    not require this artifact.

If your repository uses this same ``{PROJECT}/{BRANCH}/{FILEPATH}`` naming
scheme, the following function will work::

    def split_file_branches(path):
        pieces = path.split('/')
        if pieces[0] == 'trunk':
            return (None, '/'.join(pieces[1:]))
        elif pieces[0] == 'branches':
            return ('/'.join(pieces[0:2]),
                    '/'.join(pieces[2:]))
        else:
            return None

In fact, this is the definition of the provided ``split_file_branches``
function.  So to have our Twisted-watching :bb:chsrc:`SVNPoller` follow
multiple branches, we would use this::

    from buildbot.changes.svnpoller import SVNPoller, split_file_branches
    c['change_source'] = SVNPoller("svn://svn.twistedmatrix.com/svn/Twisted",
                                   split_file=split_file_branches)

Changes for all sorts of branches (with names like ``"branches/1.5.x"``, and
``None`` to indicate the trunk) will be delivered to the Schedulers.  Each
Scheduler is then free to use or ignore each branch as it sees fit.

BRANCHNAME/PROJECT/FILEPATH repositories
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Another common way to organize a Subversion repository is to put the branch
name at the top, and the projects underneath. This is especially frequent when
there are a number of related sub-projects that all get released in a group.

For example, `Divmod.org <http://Divmod.org>`_ hosts a project named `Nevow` as
well as one named `Quotient`. In a checked-out Nevow tree there is a directory
named `formless` that contains a python source file named :file:`webform.py`.
This repository is accessible via webdav (and thus uses an `http:` scheme)
through the divmod.org hostname. There are many branches in this repository,
and they use a ``({BRANCHNAME})/({PROJECT})`` naming policy.

The fully-qualified SVN URL for the trunk version of :file:`webform.py` is
``http://divmod.org/svn/Divmod/trunk/Nevow/formless/webform.py``.
The 1.5.x branch version of this file would have a URL of
``http://divmod.org/svn/Divmod/branches/1.5.x/Nevow/formless/webform.py``.
The whole Nevow trunk would be checked out with
``http://divmod.org/svn/Divmod/trunk/Nevow``, while the Quotient
trunk would be checked out using
``http://divmod.org/svn/Divmod/trunk/Quotient``.

Now suppose we want to have an :bb:chsrc:`SVNPoller` that only cares about the
Nevow trunk. This case looks just like the ``{PROJECT}/{BRANCH}`` layout
described earlier::

    from buildbot.changes.svnpoller import SVNPoller
    c['change_source'] = SVNPoller("http://divmod.org/svn/Divmod/trunk/Nevow")

But what happens when we want to track multiple Nevow branches? We
have to point our ``svnurl=`` high enough to see all those
branches, but we also don't want to include Quotient changes (since
we're only building Nevow). To accomplish this, we must rely upon the
``split_file`` function to help us tell the difference between
files that belong to Nevow and those that belong to Quotient, as well
as figuring out which branch each one is on. ::

    from buildbot.changes.svnpoller import SVNPoller
    c['change_source'] = SVNPoller("http://divmod.org/svn/Divmod",
                                   split_file=my_file_splitter)

The ``my_file_splitter`` function will be called with repository-relative
pathnames like:

:file:`trunk/Nevow/formless/webform.py`
    This is a Nevow file, on the trunk. We want the Change that includes this
    to see a filename of :file:`formless/webform.py`, and a branch of
    ``None``

:file:`branches/1.5.x/Nevow/formless/webform.py`
    This is a Nevow file, on a branch. We want to get
    ``branch='branches/1.5.x'`` and ``filename='formless/webform.py'``.

:file:`trunk/Quotient/setup.py`
    This is a Quotient file, so we want to ignore it by having
    :meth:`my_file_splitter` return ``None``.

:file:`branches/1.5.x/Quotient/setup.py`
    This is also a Quotient file, which should be ignored.

The following definition for :meth:`my_file_splitter` will do the job::

    def my_file_splitter(path):
        pieces = path.split('/')
        if pieces[0] == 'trunk':
            branch = None
            pieces.pop(0) # remove 'trunk'
        elif pieces[0] == 'branches':
            pieces.pop(0) # remove 'branches'
            # grab branch name
            branch = 'branches/' + pieces.pop(0)
        else:
            return None # something weird
        projectname = pieces.pop(0)
        if projectname != 'Nevow':
            return None # wrong project
        return (branch, '/'.join(pieces))

.. _Writing-Change-Sources:

Writing Change Sources
----------------------

For some version-control systems, making Bulidbot aware of new changes can be a
challenge.  If the pre-supplied classes in :ref:`Change-Sources` are not
sufficient, then you will need to write your own.

There are three approaches, one of which is not even a change source.
The first option is to write a change source that exposes some service to
which the version control system can "push" changes.  This can be more
complicated, since it requires implementing a new service, but delivers changes
to Buildbot immediately on commit.

The second option is often preferable to the first: implement a notification
service in an external process (perhaps one that is started directly by the
version control system, or by an email server) and delivers changes to Buildbot
via :ref:`PBChangeSource`.  This section does not describe this particular
approach, since it requires no customization within the buildmaster process.

The third option is to write a change source which polls for changes -
repeatedly connecting to an external service to check for new changes.  This
works well in many cases, but can produce a high load on the version control
system if polling is too frequent, and can take too long to notice changes if
the polling is not frequent enough.

Writing a Notification-based Change Source
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. py:class:: buildbot.changes.base.ChangeSource

A custom change source must implement
:class:`buildbot.interfaces.IChangeSource`.

The easiest way to do this is to subclass
:class:`buildbot.changes.base.ChangeSource`, implementing the :meth:`describe`
method to describe the instance. :class:`ChangeSource` is a Twisted service, so
you will need to implement the :meth:`startService` and :meth:`stopService`
methods to control the means by which your change source receives
notifications.

When the class does receive a change, it should call
``self.master.addChange(..)`` to submit it to the buildmaster.  This method
shares the same parameters as ``master.db.changes.addChange``, so consult the
API documentation for that function for details on the available arguments.

You will probably also want to set ``compare_attrs`` to the list of object
attributes which Buildbot will use to compare one change source to another when
reconfiguring.  During reconfiguration, if the new change source is different
from the old, then the old will be stopped and the new started.

Writing a Change Poller
~~~~~~~~~~~~~~~~~~~~~~~

.. py:class:: buildbot.changes.base.PollingChangeSource

Polling is a very common means of seeking changes, so Buildbot supplies a
utility parent class to make it easier.  A poller should subclass
:class:`buildbot.changes.base.PollingChangeSource`, which is a subclass of
:class:`ChangeSource`.  This subclass implements the :meth:`Service` methods,
and causes the :meth:`poll` method to be called every ``self.pollInterval``
seconds.  This method should return a Deferred to signal its completion.

Aside from the service methods, the other concerns in the previous section
apply here, too.

Writing a New Latent Buildslave Implementation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Writing a new latent buildslave should only require subclassing
:class:`buildbot.buildslave.AbstractLatentBuildSlave` and implementing
:meth:`start_instance` and :meth:`stop_instance`. ::

    def start_instance(self):
        # responsible for starting instance that will try to connect with this
        # master. Should return deferred. Problems should use an errback. The
        # callback value can be None, or can be an iterable of short strings to
        # include in the "substantiate success" status message, such as
        # identifying the instance that started.
        raise NotImplementedError
    
    def stop_instance(self, fast=False):
        # responsible for shutting down instance. Return a deferred. If `fast`,
        # we're trying to shut the master down, so callback as soon as is safe.
        # Callback value is ignored.
        raise NotImplementedError

See :class:`buildbot.ec2buildslave.EC2LatentBuildSlave` for an example, or see
the test example :class:`buildbot.test_slaves.FakeLatentBuildSlave`.

