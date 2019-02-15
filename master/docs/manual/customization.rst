Customization
=============

For advanced users, Buildbot acts as a framework supporting a customized build application.
For the most part, such configurations consist of subclasses set up for use in a regular Buildbot configuration file.

This chapter describes some of the more common idioms in advanced Buildbot configurations.

At the moment, this chapter is an unordered set of suggestions:

.. contents::
   :local:

If you'd like to clean it up, fork the project on GitHub and get started!

Programmatic Configuration Generation
-------------------------------------

Bearing in mind that ``master.cfg`` is a Python file, large configurations can be shortened considerably by judicious use of Python loops.
For example, the following will generate a builder for each of a range of supported versions of Python::

    pythons = ['python2.4', 'python2.5', 'python2.6', 'python2.7',
               'python3.2', 'python3.3']
    pytest_workers = ["worker%s" % n for n in range(10)]
    for python in pythons:
        f = util.BuildFactory()
        f.addStep(steps.SVN(...))
        f.addStep(steps.ShellCommand(command=[python, 'test.py']))
        c['builders'].append(util.BuilderConfig(
                name="test-%s" % python,
                factory=f,
                workernames=pytest_workers))

Next step would be the loading of ``pythons`` list from a .yaml/.ini file.

.. _Collapse-Request-Functions:

Collapse Request Functions
--------------------------

.. index:: Builds; collapsing


The logic Buildbot uses to decide which build request can be merged can be customized by providing a Python function (a callable) instead of ``True`` or ``False`` described in :ref:`Collapsing-Build-Requests`.

Arguments for the callable are:

    ``master``
        pointer to the master object, which can be used to make additional data api calls via `master.data.get`

    ``builder``
        dictionary of type :bb:rtype:`builder`

    ``req1``
        dictionary of type :bb:rtype:`buildrequest`

    ``req2``
        dictionary of type :bb:rtype:`buildrequest`

.. warning::

    The number of invocations of the callable is proportional to the square of the request queue length, so a long-running callable may cause undesirable delays when the queue length grows.

It should return true if the requests can be merged, and False otherwise.
For example::

    @defer.inlineCallbacks
    def collapseRequests(master, builder, req1, req2):
        "any requests with the same branch can be merged"

        # get the buildsets for each buildrequest
        selfBuildset , otherBuildset = yield defer.gatherResults([
            master.data.get(('buildsets', req1['buildsetid'])),
            master.data.get(('buildsets', req2['buildsetid']))
            ])
        selfSourcestamps = selfBuildset['sourcestamps']
        otherSourcestamps = otherBuildset['sourcestamps']

        if len(selfSourcestamps) != len(otherSourcestamps):
            return False

        for selfSourcestamp, otherSourcestamp in zip(selfSourcestamps, otherSourcestamps):
            if selfSourcestamp['branch'] != otherSourcestamp['branch']:
                return False

        return True

    c['collapseRequests'] = collapseRequests

In many cases, the details of the :bb:rtype:`sourcestamp` and :bb:rtype:`buildrequest` are important.

In the following example, only :bb:rtype:`buildrequest` with the same "reason" are merged; thus developers forcing builds for different reasons will see distinct builds.

Note the use of the :py:meth:`buildrequest.BuildRequest.canBeCollapsed` method to access the source stamp compatibility algorithm.

::

    @defer.inlineCallbacks
    def collapseRequests(master, builder, req1, req2):
        canBeCollapsed = yield buildrequest.BuildRequest.canBeCollapsed(master, req1, req2)
        if canBeCollapsed and req1.reason == req2.reason:
           return True
        else:
           return False
    c['collapseRequests'] = collapseRequests

Another common example is to prevent collapsing of requests coming from a :bb:step:`Trigger` step.
:bb:step:`Trigger` step can indeed be used in order to implement parallel testing of the same source.

Buildrequests will all have the same sourcestamp, but probably different properties, and shall not be collapsed.

.. note::

    In most of the cases, just setting collapseRequests=False for triggered builders will do the trick.

In other cases, ``parent_buildid`` from buildset can be used::

    @defer.inlineCallbacks
    def collapseRequests(master, builder, req1, req2):
        canBeCollapsed = yield buildrequest.BuildRequest.canBeCollapsed(master, req1, req2)
        selfBuildset , otherBuildset = yield defer.gatherResults([
            master.data.get(('buildsets', req1['buildsetid'])),
            master.data.get(('buildsets', req2['buildsetid']))
        ])
        if canBeCollapsed and selfBuildset['parent_buildid'] != None and otherBuildset['parent_buildid'] != None:
           return True
        else:
           return False
    c['collapseRequests'] = collapseRequests


If it's necessary to perform some extended operation to determine whether two requests can be merged, then the ``collapseRequests`` callable may return its result via Deferred.

.. warning::

    Again, the number of invocations of the callable is proportional to the square of the request queue length, so a long-running callable may cause undesirable delays when the queue length grows.

For example::

    @defer.inlineCallbacks
    def collapseRequests(master, builder, req1, req2):
        info1, info2 = yield defer.gatherResults([
            getMergeInfo(req1),
            getMergeInfo(req2),
        ])
        return info1 == info2

    c['collapseRequests'] = collapseRequests

.. _Builder-Priority-Functions:

Builder Priority Functions
--------------------------

.. index:: Builders; priority

The :bb:cfg:`prioritizeBuilders` configuration key specifies a function which is called with two arguments: a :class:`BuildMaster` and a list of :class:`Builder` objects.
It should return a list of the same :class:`Builder` objects, in the desired order.
It may also remove items from the list if builds should not be started on those builders.
If necessary, this function can return its results via a Deferred (it is called with ``maybeDeferred``).

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

If the change frequency is higher than the turn-around of the builders,
the following approach might be helpful:

.. code-block:: python

    def prioritizeBuilders(buildmaster, builders):
        """Prioritize builders. First, prioritize inactive builders.
        Second, consider the last time a job was completed (no job is infinite past).
        Third, consider the time the oldest request has been queued.
        This provides a simple round-robin scheme that works with collapsed builds."""

        def isBuilding(b):
            return bool(b.building) or bool(b.old_building)

        builders.sort(key = lambda b: (isBuilding(b), b.getNewestCompleteTime(), b.getOldestRequestTime()))
        return builders

    c['prioritizeBuilders'] = prioritizeBuilders


.. index:: Builds; priority

.. _Build-Priority-Functions:

Build Priority Functions
------------------------

When a builder has multiple pending build requests, it uses a ``nextBuild`` function to decide which build it should start first.
This function is given two parameters: the :class:`Builder`, and a list of :class:`BuildRequest` objects representing pending build requests.

A simple function to prioritize release builds over other builds might look like this::

   def nextBuild(bldr, requests):
       for r in requests:
           if r.source.branch == 'release':
               return r
       return requests[0]

If some non-immediate result must be calculated, the ``nextBuild`` function can also return a Deferred::

    def nextBuild(bldr, requests):
        d = get_request_priorities(requests)
        def pick(priorities):
            if requests:
                return sorted(zip(priorities, requests))[0][1]
        d.addCallback(pick)
        return d

The ``nextBuild`` function is passed as parameter to :class:`BuilderConfig`::

    ... BuilderConfig(..., nextBuild=nextBuild, ...) ...

.. _canStartBuild-Functions:

``canStartBuild`` Functions
---------------------------

Sometimes, you cannot know in advance what workers to assign to a :class:`BuilderConfig`.
For example, you might need to check for the existence of a file on a worker before running a build on it.
It is possible to do that by setting the ``canStartBuild`` callback.

Here is an example that checks if there is a ``vm`` property set for the build request.
If it is set, it checks if a file named after it exists in the ``/opt/vm`` folder.
If the file does not exist on the given worker, refuse to run the build to force the master to select another worker.

.. code-block:: python

   @defer.inlineCallbacks
   def canStartBuild(builder, wfb, request):

       vm = request.properties.get('vm', builder.config.properties.get('vm'))
       if vm:
           args = {'file': os.path.join('/opt/vm', vm)}
           cmd = RemoteCommand('stat', args, stdioLogName=None)
           cmd.worker = wfb.worker
           res = yield cmd.run(None, wfb.worker.conn, builder.name)
           if res.rc != 0:
               return False

       return True

Here is a more complete example that checks if a worker is fit to start a build.
If the load average is higher than the number of CPU cores or if there is less than 2GB of free memory, refuse to run the build on that worker.
Also, put that worker in quarantine to make sure no other builds are scheduled on it for a while.
Otherwise, let the build start on that worker.

.. code-block:: python

   class FakeBuild(object):
       properties = Properties()

   class FakeStep(object):
       build = FakeBuild()

   @defer.inlineCallbacks
   def shell(command, worker, builder):
       args = {
           'command': command,
           'logEnviron': False,
           'workdir': worker.worker_basedir,
           'want_stdout': False,
           'want_stderr': False,
       }
       cmd = RemoteCommand('shell', args, stdioLogName=None)
       cmd.worker = worker
       yield cmd.run(FakeStep(), worker.conn, builder.name)
       return cmd.rc

   @defer.inlineCallbacks
   def canStartBuild(builder, wfb, request):
       # check that load is not too high
       rc = yield shell(
           'test "$(cut -d. -f1 /proc/loadavg)" -le "$(nproc)"',
           wfb.worker, builder)
       if rc != 0:
           log.msg('loadavg is too high to take new builds',
                   system=repr(wfb.worker))
           wfb.worker.putInQuarantine()
           return False

       # check there is enough free memory
       sed_expr = r's/^MemAvailable:[[:space:]]+([0-9]+)[[:space:]]+kB$/\1/p'
       rc = yield shell(
           'test "$(sed -nre \'%s\' /proc/meminfo)" -gt 2000000' % sed_expr,
           wfb.worker, builder)
       if rc != 0:
           log.msg('not enough free memory to take new builds',
                   system=repr(wfb.worker))
           wfb.worker.putInQuarantine()
           return False

       # The build may now proceed.
       #
       # Prevent this worker from taking any other build while this one is
       # starting for 2 min. This leaves time for the build to start consuming
       # resources (disk, memory, cpu). When the quarantine is over, if the
       # same worker is subject to start another build, the above checks will
       # better reflect the actual state of the worker.
       wfb.worker.quarantine_timeout = 120
       wfb.worker.putInQuarantine()

       # This does not take the worker out of quarantine, it only resets the
       # timeout value to default.
       wfb.worker.resetQuarantine()

       return True

You can extend these examples using any remote command described in the :doc:`../developer/master-worker`.

.. _Customizing-SVNPoller:

Customizing SVNPoller
---------------------

Each source file that is tracked by a Subversion repository has a fully-qualified SVN URL in the following form: :samp:`({REPOURL})({PROJECT-plus-BRANCH})({FILEPATH})`.
When you create the :bb:chsrc:`SVNPoller`, you give it a ``repourl`` value that includes all of the :samp:`{REPOURL}` and possibly some portion of the :samp:`{PROJECT-plus-BRANCH}` string.
The :bb:chsrc:`SVNPoller` is responsible for producing Changes that contain a branch name and a :samp:`{FILEPATH}` (which is relative to the top of a checked-out tree).
The details of how these strings are split up depend upon how your repository names its branches.

:samp:`{PROJECT}/{BRANCHNAME}/{FILEPATH}` repositories
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

One common layout is to have all the various projects that share a repository get a single top-level directory each, with ``branches``, ``tags``, and ``trunk`` subdirectories:

.. code-block:: none

    amanda/trunk
          /branches/3_2
                   /3_3
          /tags/3_2_1
               /3_2_2
               /3_3_0

To set up a :bb:chsrc:`SVNPoller` that watches the Amanda trunk (and nothing else), we would use the following, using the default ``split_file``::

    from buildbot.plugins import changes
    c['change_source'] = changes.SVNPoller(
       repourl="https://svn.amanda.sourceforge.net/svnroot/amanda/amanda/trunk")

In this case, every Change that our :bb:chsrc:`SVNPoller` produces will have its branch attribute set to ``None``, to indicate that the Change is on the trunk.
No other sub-projects or branches will be tracked.

If we want our ChangeSource to follow multiple branches, we have to do two things.
First we have to change our ``repourl=`` argument to watch more than just ``amanda/trunk``.
We will set it to ``amanda`` so that we'll see both the trunk and all the branches.
Second, we have to tell :bb:chsrc:`SVNPoller` how to split the :samp:`({PROJECT-plus-BRANCH})({FILEPATH})` strings it gets from the repository out into :samp:`({BRANCH})` and :samp:`({FILEPATH})`.

We do the latter by providing a ``split_file`` function.
This function is responsible for splitting something like ``branches/3_3/common-src/amanda.h`` into ``branch='branches/3_3'`` and ``filepath='common-src/amanda.h'``.
The function is always given a string that names a file relative to the subdirectory pointed to by the :bb:chsrc:`SVNPoller`\'s ``repourl=`` argument.
It is expected to return a dictionary with at least the ``path`` key.
The splitter may optionally set ``branch``, ``project`` and ``repository``.
For backwards compatibility it may return a tuple of ``(branchname, path)``.
It may also return ``None`` to indicate that the file is of no interest.

.. note::

   The function should return ``branches/3_3`` rather than just ``3_3`` because the SVN checkout step, will append the branch name to the ``baseURL``, which requires that we keep the ``branches`` component in there.
   Other VC schemes use a different approach towards branches and may not require this artifact.

If your repository uses this same ``{PROJECT}/{BRANCH}/{FILEPATH}`` naming scheme, the following function will work::

    def split_file_branches(path):
        pieces = path.split('/')
        if len(pieces) > 1 and pieces[0] == 'trunk':
            return (None, '/'.join(pieces[1:]))
        elif len(pieces) > 2 and pieces[0] == 'branches':
            return ('/'.join(pieces[0:2]),
                    '/'.join(pieces[2:]))
        else:
            return None

In fact, this is the definition of the provided ``split_file_branches`` function.
So to have our Twisted-watching :bb:chsrc:`SVNPoller` follow multiple branches, we would use this::

    from buildbot.plugins import changes, util
    c['change_source'] = changes.SVNPoller("svn://svn.twistedmatrix.com/svn/Twisted",
                                           split_file=util.svn.split_file_branches)

Changes for all sorts of branches (with names like ``"branches/1.5.x"``, and ``None`` to indicate the trunk) will be delivered to the Schedulers.
Each Scheduler is then free to use or ignore each branch as it sees fit.

If you have multiple projects in the same repository your split function can attach a project name to the Change to help the Scheduler filter out unwanted changes::

    from buildbot.plugins import util
    def split_file_projects_branches(path):
        if not "/" in path:
            return None
        project, path = path.split("/", 1)
        f = util.svn.split_file_branches(path)
        if f:
            info = dict(project=project, path=f[1])
            if f[0]:
                info['branch'] = f[0]
            return info
        return f

Again, this is provided by default.
To use it you would do this::

    from buildbot.plugins import changes, util
    c['change_source'] = changes.SVNPoller(
       repourl="https://svn.amanda.sourceforge.net/svnroot/amanda/",
       split_file=util.svn.split_file_projects_branches)

Note here that we are monitoring at the root of the repository, and that within that repository is a ``amanda`` subdirectory which in turn has ``trunk`` and ``branches``.
It is that ``amanda`` subdirectory whose name becomes the ``project`` field of the Change.


:samp:`{BRANCHNAME}/{PROJECT}/{FILEPATH}` repositories
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Another common way to organize a Subversion repository is to put the branch name at the top, and the projects underneath.
This is especially frequent when there are a number of related sub-projects that all get released in a group.

For example, ``Divmod.org`` hosts a project named `Nevow` as well as one named `Quotient`.
In a checked-out Nevow tree there is a directory named `formless` that contains a Python source file named :file:`webform.py`.
This repository is accessible via webdav (and thus uses an `http:` scheme) through the divmod.org hostname.
There are many branches in this repository, and they use a ``({BRANCHNAME})/({PROJECT})`` naming policy.

The fully-qualified SVN URL for the trunk version of :file:`webform.py` is ``http://divmod.org/svn/Divmod/trunk/Nevow/formless/webform.py``.
The 1.5.x branch version of this file would have a URL of ``http://divmod.org/svn/Divmod/branches/1.5.x/Nevow/formless/webform.py``.
The whole Nevow trunk would be checked out with ``http://divmod.org/svn/Divmod/trunk/Nevow``, while the Quotient trunk would be checked out using ``http://divmod.org/svn/Divmod/trunk/Quotient``.

Now suppose we want to have an :bb:chsrc:`SVNPoller` that only cares about the Nevow trunk.
This case looks just like the :samp:`{PROJECT}/{BRANCH}` layout described earlier::

    from buildbot.plugins import changes
    c['change_source'] = changes.SVNPoller("http://divmod.org/svn/Divmod/trunk/Nevow")

But what happens when we want to track multiple Nevow branches?
We have to point our ``repourl=`` high enough to see all those branches, but we also don't want to include Quotient changes (since we're only building Nevow).
To accomplish this, we must rely upon the ``split_file`` function to help us tell the difference between files that belong to Nevow and those that belong to Quotient, as well as figuring out which branch each one is on.

::

    from buildbot.plugins import changes
    c['change_source'] = changes.SVNPoller("http://divmod.org/svn/Divmod",
                                           split_file=my_file_splitter)

The ``my_file_splitter`` function will be called with repository-relative pathnames like:

:file:`trunk/Nevow/formless/webform.py`
    This is a Nevow file, on the trunk.
    We want the Change that includes this to see a filename of :file:`formless/webform.py`, and a branch of ``None``

:file:`branches/1.5.x/Nevow/formless/webform.py`
    This is a Nevow file, on a branch.
    We want to get ``branch='branches/1.5.x'`` and ``filename='formless/webform.py'``.

:file:`trunk/Quotient/setup.py`
    This is a Quotient file, so we want to ignore it by having :meth:`my_file_splitter` return ``None``.

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
        return dict(branch=branch, path='/'.join(pieces))

If you later decide you want to get changes for Quotient as well you could replace the last 3 lines with simply::

    return dict(project=projectname, branch=branch, path='/'.join(pieces))


.. _Writing-Change-Sources:

Writing Change Sources
----------------------

For some version-control systems, making Buildbot aware of new changes can be a challenge.
If the pre-supplied classes in :ref:`Change-Sources` are not sufficient, then you will need to write your own.

There are three approaches, one of which is not even a change source.
The first option is to write a change source that exposes some service to which the version control system can "push" changes.
This can be more complicated, since it requires implementing a new service, but delivers changes to Buildbot immediately on commit.

The second option is often preferable to the first: implement a notification service in an external process (perhaps one that is started directly by the version control system, or by an email server) and delivers changes to Buildbot via :ref:`PBChangeSource`.
This section does not describe this particular approach, since it requires no customization within the buildmaster process.

The third option is to write a change source which polls for changes - repeatedly connecting to an external service to check for new changes.
This works well in many cases, but can produce a high load on the version control system if polling is too frequent, and can take too long to notice changes if the polling is not frequent enough.

Writing a Notification-based Change Source
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A custom change source must implement :class:`buildbot.interfaces.IChangeSource`.

The easiest way to do this is to subclass :class:`buildbot.changes.base.ChangeSource`, implementing the :meth:`describe` method to describe the instance.
:class:`ChangeSource` is a Twisted service, so you will need to implement the :meth:`startService` and :meth:`stopService` methods to control the means by which your change source receives notifications.

When the class does receive a change, it should call ``self.master.data.updates.addChange(..)`` to submit it to the buildmaster.
This method shares the same parameters as ``master.db.changes.addChange``, so consult the API documentation for that function for details on the available arguments.

You will probably also want to set ``compare_attrs`` to the list of object attributes which Buildbot will use to compare one change source to another when reconfiguring.
During reconfiguration, if the new change source is different from the old, then the old will be stopped and the new started.

Writing a Change Poller
~~~~~~~~~~~~~~~~~~~~~~~

Polling is a very common means of seeking changes, so Buildbot supplies a utility parent class to make it easier.
A poller should subclass :class:`buildbot.changes.base.PollingChangeSource`, which is a subclass of :class:`~buildbot.changes.base.ChangeSource`.
This subclass implements the :meth:`Service` methods, and calls the :meth:`poll` method according to the ``pollInterval`` and ``pollAtLaunch`` options.
The ``poll`` method should return a Deferred to signal its completion.

Aside from the service methods, the other concerns in the previous section apply here, too.

Writing a New Latent Worker Implementation
------------------------------------------

Writing a new latent worker should only require subclassing :class:`buildbot.worker.AbstractLatentWorker` and implementing :meth:`start_instance` and :meth:`stop_instance` at a minimum.

.. bb:worker:: AbstractWorkerController

AbstractLatentWorker
~~~~~~~~~~~~~~~~~~~~

.. py:class:: buildbot.worker.AbstractLatentWorker

This class is the base class of all latent workers and implements some common functionality.
A custom worker should only need to override :meth:`start_instance` and :meth:`stop_instance` methods.

See :class:`buildbot.worker.ec2.EC2LatentWorker` for an example.

Additionally, :meth:`builds_may_be_incompatible` and :attr:`isCompatibleWithBuild` members must be overridden if some qualities of the new instances is determined dynamically according to the properties of an incoming build.
An example a build may require a certain Docker image or amount of allocated memory.
Overriding these members ensures that builds aren't ran on incompatible workers that have already been started.

    .. py:method:: start_instance(self)

        This method is responsible for starting instance that will try to connect with this master.
        A deferred should be returned.
        Any problems should use an errback.
        The callback value can be ``None``, or can be an iterable of short strings to include in the "substantiate success" status message, such as identifying the instance that started.
        Buildbot will ensure that a single worker will never have its ``start_instance`` called before any previous calls to ``start_instance`` or ``stop_instance`` finish.
        Additionally, for each ``start_instance`` call, exactly one corresponding call to ``stop_instance`` will be done eventually.

    .. py:method:: stop_instance(self, fast=False)

        This method is responsible for shutting down instance.
        A deferred should be returned.
        If ``fast`` is ``True`` then the function should call back as soon as it is safe to do so, as, for example, the master may be shutting down.
        The value returned by the callback is ignored.
        Buildbot will ensure that a single worker will never have its ``stop_instance`` called before any previous calls to ``stop_instance`` finish.
        ``stop_instance`` may be called before ``start_instance`` finishes only if ``start_instance`` takes a long time and the worker times out.

    .. py:attribute:: builds_may_be_incompatible

        Determines if new instances have qualities dependent on the build.
        If ``True``, the master will call ``isCompatibleWithBuild`` to determine whether new builds are compatible with the started instance.
        Unnecessarily setting ``builds_may_be_incompatible`` to ``True`` may result in unnecessary overhead when processing the builds.
        By default, this is ``False``.

    .. py:method:: isCompatibleWithBuild(self, build_props)

        This method determines whether a started instance is compatible with the build that is about to be started.
        ``build_props`` is the properties of the build that are known before the build has been started.
        A build may be incompatible with already started instance if, for example, it requests a different amount of memory or a different Docker image.
        A deferred should be returned, whose callback should return ``True`` if build is compatible and ``False`` otherwise.
        The method may be called when the instance is not yet started and should indicate compatible build in that case.
        In the default implementation the callback returns ``True``.

Custom Build Classes
--------------------

The standard :class:`BuildFactory` object creates :class:`Build` objects by default.
These Builds will each execute a collection of :class:`BuildStep`\s in a fixed sequence.
Each step can affect the results of the build, but in general there is little intelligence to tie the different steps together.

By setting the factory's ``buildClass`` attribute to a different class, you can instantiate a different build class.
This might be useful, for example, to create a build class that dynamically determines which steps to run.
The skeleton of such a project would look like::

    class DynamicBuild(Build):
        # override some methods
        ...

    f = factory.BuildFactory()
    f.buildClass = DynamicBuild
    f.addStep(...)

.. _Factory-Workdir-Functions:

Factory Workdir Functions
-------------------------

.. note::

    While factory workdir function is still supported, it is better to just use the fact that workdir is a :index:`renderables <renderable>` attribute of every steps.
    A Renderable has access to much more contextual information, and also can return a deferred.
    So you could say ``build_factory.workdir = util.Interpolate("%(src:repository)s`` to achieve similar goal.

It is sometimes helpful to have a build's workdir determined at runtime based on the parameters of the build.
To accomplish this, set the ``workdir`` attribute of the build factory to a callable.
That callable will be invoked with the list of :class:`SourceStamp` for the build, and should return the appropriate workdir.
Note that the value must be returned immediately - Deferreds are not supported.

This can be useful, for example, in scenarios with multiple repositories submitting changes to Buildbot.
In this case you likely will want to have a dedicated workdir per repository, since otherwise a sourcing step with mode = "update" will fail as a workdir with a working copy of repository A can't be "updated" for changes from a repository B.
Here is an example how you can achieve workdir-per-repo::

        def workdir(source_stamps):
            return hashlib.md5(source_stamps[0].repository).hexdigest()[:8]

        build_factory = factory.BuildFactory()
        build_factory.workdir = workdir

        build_factory.addStep(Git(mode="update"))
        # ...
        builders.append ({'name': 'mybuilder',
                          'workername': 'myworker',
                          'builddir': 'mybuilder',
                          'factory': build_factory})

The end result is a set of workdirs like

.. code-block:: none

    Repo1 => <worker-base>/mybuilder/a78890ba
    Repo2 => <worker-base>/mybuilder/0823ba88

You could make the :func:`workdir()` function compute other paths, based on parts of the repo URL in the sourcestamp, or lookup in a lookup table based on repo URL.
As long as there is a permanent 1:1 mapping between repos and workdir, this will work.

.. _Writing-New-BuildSteps:

Writing New BuildSteps
----------------------

.. warning::

   The API of writing custom build steps has changed significantly in Buildbot-0.9.0.
   See :ref:`New-Style-Build-Steps` for details about what has changed since pre 0.9.0 releases.
   This section documents new-style steps.

While it is a good idea to keep your build process self-contained in the source code tree, sometimes it is convenient to put more intelligence into your Buildbot configuration.
One way to do this is to write a custom :class:`~buildbot.process.buildstep.BuildStep`.
Once written, this Step can be used in the :file:`master.cfg` file.

The best reason for writing a custom :class:`BuildStep` is to better parse the results of the command being run.
For example, a :class:`~buildbot.process.buildstep.BuildStep` that knows about JUnit could look at the logfiles to determine which tests had been run, how many passed and how many failed, and then report more detailed information than a simple ``rc==0`` -based `good/bad` decision.

Buildbot has acquired a large fleet of build steps, and sports a number of knobs and hooks to make steps easier to write.
This section may seem a bit overwhelming, but most custom steps will only need to apply one or two of the techniques outlined here.

For complete documentation of the build step interfaces, see :doc:`../developer/cls-buildsteps`.

.. _Writing-BuildStep-Constructors:

Writing BuildStep Constructors
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Build steps act as their own factories, so their constructors are a bit more complex than necessary.
The configuration file instantiates a :class:`~buildbot.process.buildstep.BuildStep` object, but the step configuration must be re-used for multiple builds, so Buildbot needs some way to create more steps.

Consider the use of a :class:`BuildStep` in :file:`master.cfg`::

    f.addStep(MyStep(someopt="stuff", anotheropt=1))

This creates a single instance of class ``MyStep``.
However, Buildbot needs a new object each time the step is executed.
An instance of :class:`~buildbot.process.buildstep.BuildStep` remembers how it was constructed, and can create copies of itself.
When writing a new step class, then, keep in mind are that you cannot do anything "interesting" in the constructor -- limit yourself to checking and storing arguments.

It is customary to call the parent class's constructor with all otherwise-unspecified keyword arguments.
Keep a ``**kwargs`` argument on the end of your options, and pass that up to the parent class's constructor.

The whole thing looks like this::

    class Frobnify(LoggingBuildStep):
        def __init__(self,
                frob_what="frobee",
                frob_how_many=None,
                frob_how=None,
                **kwargs):

            # check
            if frob_how_many is None:
                raise TypeError("Frobnify argument how_many is required")

            # override a parent option
            kwargs['parentOpt'] = 'xyz'

            # call parent
            super().__init__(**kwargs)

            # set Frobnify attributes
            self.frob_what = frob_what
            self.frob_how_many = how_many
            self.frob_how = frob_how

    class FastFrobnify(Frobnify):
        def __init__(self,
                speed=5,
                **kwargs):
            super().__init__(**kwargs)
            self.speed = speed

Step Execution Process
~~~~~~~~~~~~~~~~~~~~~~

A step's execution occurs in its :py:meth:`~buildbot.process.buildstep.BuildStep.run` method.
When this method returns (more accurately, when the Deferred it returns fires), the step is complete.
The method's result must be an integer, giving the result of the step.
Any other output from the step (logfiles, status strings, URLs, etc.) is the responsibility of the ``run`` method.

The :bb:step:`ShellCommand` class implements this ``run`` method, and in most cases steps subclassing ``ShellCommand`` simply implement some of the subsidiary methods that its ``run`` method calls.

Running Commands
~~~~~~~~~~~~~~~~

To spawn a command in the worker, create a :class:`~buildbot.process.remotecommand.RemoteCommand` instance in your step's ``run`` method and run it with :meth:`~buildbot.process.remotecommand.BuildStep.runCommand`::

    cmd = RemoteCommand(args)
    d = self.runCommand(cmd)

The :py:class:`~buildbot.process.buildstep.CommandMixin` class offers a simple interface to several common worker-side commands.

For the much more common task of running a shell command on the worker, use :py:class:`~buildbot.process.buildstep.ShellMixin`.
This class provides a method to handle the myriad constructor arguments related to shell commands, as well as a method to create new :py:class:`~buildbot.process.remotecommand.RemoteCommand` instances.
This mixin is the recommended method of implementing custom shell-based steps.
The older pattern of subclassing ``ShellCommand`` is no longer recommended.

A simple example of a step using the shell mixin is::

    class RunCleanup(buildstep.ShellMixin, buildstep.BuildStep):
        def __init__(self, cleanupScript='./cleanup.sh', **kwargs):
            self.cleanupScript = cleanupScript
            kwargs = self.setupShellMixin(kwargs, prohibitArgs=['command'])
            super().__init__(**kwargs)

        @defer.inlineCallbacks
        def run(self):
            cmd = yield self.makeRemoteShellCommand(
                    command=[self.cleanupScript])
            yield self.runCommand(cmd)
            if cmd.didFail():
                cmd = yield self.makeRemoteShellCommand(
                        command=[self.cleanupScript, '--force'],
                        logEnviron=False)
                yield self.runCommand(cmd)
            return cmd.results()

    @defer.inlineCallbacks
    def run(self):
        cmd = RemoteCommand(args)
        log = yield self.addLog('output')
        cmd.useLog(log, closeWhenFinished=True)
        yield self.runCommand(cmd)

Updating Status Strings
~~~~~~~~~~~~~~~~~~~~~~~

Each step can summarize its current status in a very short string.
For example, a compile step might display the file being compiled.
This information can be helpful users eager to see their build finish.

Similarly, a build has a set of short strings collected from its steps summarizing the overall state of the build.
Useful information here might include the number of tests run, but probably not the results of a ``make clean`` step.

As a step runs, Buildbot calls its :py:meth:`~buildbot.process.buildstep.BuildStep.getCurrentSummary` method as necessary to get the step's current status.
"As necessary" is determined by calls to :py:meth:`buildbot.process.buildstep.BuildStep.updateSummary`.
Your step should call this method every time the status summary may have changed.
Buildbot will take care of rate-limiting summary updates.

When the step is complete, Buildbot calls its :py:meth:`~buildbot.process.buildstep.BuildStep.getResultSummary` method to get a final summary of the step along with a summary for the build.

About Logfiles
~~~~~~~~~~~~~~

Each BuildStep has a collection of log files.
Each one has a short name, like `stdio` or `warnings`.
Each log file contains an arbitrary amount of text, usually the contents of some output file generated during a build or test step, or a record of everything that was printed to :file:`stdout`/:file:`stderr` during the execution of some command.

Each can contain multiple `channels`, generally limited to three basic ones: stdout, stderr, and `headers`.
For example, when a shell command runs, it writes a few lines to the headers channel to indicate the exact argv strings being run, which directory the command is being executed in, and the contents of the current environment variables.
Then, as the command runs, it adds a lot of :file:`stdout` and :file:`stderr` messages.
When the command finishes, a final `header` line is added with the exit code of the process.

Status display plugins can format these different channels in different ways.
For example, the web page shows log files as text/html, with header lines in blue text, stdout in black, and stderr in red.
A different URL is available which provides a text/plain format, in which stdout and stderr are collapsed together, and header lines are stripped completely.
This latter option makes it easy to save the results to a file and run :command:`grep` or whatever against the output.

Writing Log Files
~~~~~~~~~~~~~~~~~

Most commonly, logfiles come from commands run on the worker.
Internally, these are configured by supplying the :class:`~buildbot.process.remotecommand.RemoteCommand` instance with log files via the :meth:`~buildbot.process.remoteCommand.RemoteCommand.useLog` method::

    @defer.inlineCallbacks
    def run(self):
        ...
        log = yield self.addLog('stdio')
        cmd.useLog(log, closeWhenFinished=True, 'stdio')
        yield self.runCommand(cmd)

The name passed to :meth:`~buildbot.process.remoteCommand.RemoteCommand.useLog` must match that configured in the command.
In this case, ``stdio`` is the default.

If the log file was already added by another part of the step, it can be retrieved with :meth:`~buildbot.process.buildstep.BuildStep.getLog`::

    stdioLog = self.getLog('stdio')

Less frequently, some master-side processing produces a log file.
If this log file is short and easily stored in memory, this is as simple as a call to :meth:`~buildbot.process.buildstep.BuildStep.addCompleteLog`::

    @defer.inlineCallbacks
    def run(self):
        ...
        summary = u'\n'.join('%s: %s' % (k, count)
                             for (k, count) in self.lint_results.items())
        yield self.addCompleteLog('summary', summary)

Note that the log contents must be a unicode string.

Longer logfiles can be constructed line-by-line using the ``add`` methods of the log file::

    @defer.inlineCallbacks
    def run(self):
        ...
        updates = yield self.addLog('updates')
        while True:
            ...
            yield updates.addStdout(some_update)

Again, note that the log input must be a unicode string.

Finally, :meth:`~buildbot.process.buildstep.BuildStep.addHTMLLog` is similar to :meth:`~buildbot.process.buildstep.BuildStep.addCompleteLog`, but the resulting log will be tagged as containing HTML.
The web UI will display the contents of the log using the browser.

The ``logfiles=`` argument to :bb:step:`ShellCommand` and its subclasses creates new log files and fills them in realtime by asking the worker to watch a actual file on disk.
The worker will look for additions in the target file and report them back to the :class:`BuildStep`.
These additions will be added to the log file by calling :meth:`addStdout`.

All log files can be used as the source of a :class:`~buildbot.process.logobserver.LogObserver` just like the normal :file:`stdio` :class:`LogFile`.
In fact, it's possible for one :class:`~buildbot.process.logobserver.LogObserver` to observe a logfile created by another.

Reading Logfiles
~~~~~~~~~~~~~~~~

For the most part, Buildbot tries to avoid loading the contents of a log file into memory as a single string.
For large log files on a busy master, this behavior can quickly consume a great deal of memory.

Instead, steps should implement a :class:`~buildbot.process.logobserver.LogObserver` to examine log files one chunk or line at a time.

For commands which only produce a small quantity of output, :class:`~buildbot.process.remotecommand.RemoteCommand` will collect the command's stdout into its :attr:`~buildbot.process.remotecommand.RemoteCommand.stdout` attribute if given the ``collectStdout=True`` constructor argument.

.. _Adding-LogObservers:

Adding LogObservers
~~~~~~~~~~~~~~~~~~~

Most shell commands emit messages to stdout or stderr as they operate, especially if you ask them nicely with a option `--verbose` flag of some sort.
They may also write text to a log file while they run.
Your :class:`BuildStep` can watch this output as it arrives, to keep track of how much progress the command has made or to process log output for later summarization.

To accomplish this, you will need to attach a :class:`~buildbot.process.logobserver.LogObserver` to the log.
This observer is given all text as it is emitted from the command, and has the opportunity to parse that output incrementally.

There are a number of pre-built :class:`~buildbot.process.logobserver.LogObserver` classes that you can choose from (defined in :mod:`buildbot.process.buildstep`, and of course you can subclass them to add further customization.
The :class:`LogLineObserver` class handles the grunt work of buffering and scanning for end-of-line delimiters, allowing your parser to operate on complete :file:`stdout`/:file:`stderr` lines.

For example, let's take a look at the :class:`TrialTestCaseCounter`, which is used by the :bb:step:`Trial` step to count test cases as they are run.
As Trial executes, it emits lines like the following:

.. code-block:: none

    buildbot.test.test_config.ConfigTest.testDebugPassword ... [OK]
    buildbot.test.test_config.ConfigTest.testEmpty ... [OK]
    buildbot.test.test_config.ConfigTest.testIRC ... [FAIL]
    buildbot.test.test_config.ConfigTest.testLocks ... [OK]

When the tests are finished, trial emits a long line of `======` and then some lines which summarize the tests that failed.
We want to avoid parsing these trailing lines, because their format is less well-defined than the `[OK]` lines.

A simple version of the parser for this output looks like this.
The full version is in :src:`master/buildbot/steps/python_twisted.py`.

.. code-block:: python

    from buildbot.plugins import util

    class TrialTestCaseCounter(util.LogLineObserver):
        _line_re = re.compile(r'^([\w\.]+) \.\.\. \[([^\]]+)\]$')
        numTests = 0
        finished = False

        def outLineReceived(self, line):
            if self.finished:
                return
            if line.startswith("=" * 40):
                self.finished = True
                return

            m = self._line_re.search(line.strip())
            if m:
                testname, result = m.groups()
                self.numTests += 1
                self.step.setProgress('tests', self.numTests)

This parser only pays attention to stdout, since that's where trial writes the progress lines.
It has a mode flag named ``finished`` to ignore everything after the ``====`` marker, and a scary-looking regular expression to match each line while hopefully ignoring other messages that might get displayed as the test runs.

Each time it identifies a test has been completed, it increments its counter and delivers the new progress value to the step with ``self.step.setProgress``.
This helps Buildbot to determine the ETA for the step.

To connect this parser into the :bb:step:`Trial` build step, ``Trial.__init__`` ends with the following clause::

    # this counter will feed Progress along the 'test cases' metric
    counter = TrialTestCaseCounter()
    self.addLogObserver('stdio', counter)
    self.progressMetrics += ('tests',)

This creates a :class:`TrialTestCaseCounter` and tells the step that the counter wants to watch the :file:`stdio` log.
The observer is automatically given a reference to the step in its :attr:`step` attribute.

Using Properties
~~~~~~~~~~~~~~~~

In custom :class:`BuildSteps`, you can get and set the build properties with the :meth:`getProperty` and :meth:`setProperty` methods.
Each takes a string for the name of the property, and returns or accepts an arbitrary JSON-able (lists, dicts, strings, and numbers) object.
For example::

    class MakeTarball(ShellCommand):
        def start(self):
            if self.getProperty("os") == "win":
                self.setCommand([ ... ]) # windows-only command
            else:
                self.setCommand([ ... ]) # equivalent for other systems
            super().start()

Remember that properties set in a step may not be available until the next step begins.
In particular, any :class:`Property` or :class:`Interpolate` instances for the current step are interpolated before the step starts, so they cannot use the value of any properties determined in that step.

.. index:: links, BuildStep URLs, addURL

Using Statistics
~~~~~~~~~~~~~~~~

Statistics can be generated for each step, and then summarized across all steps in a build.
For example, a test step might set its ``warnings`` statistic to the number of warnings observed.
The build could then sum the ``warnings`` on all steps to get a total number of warnings.

Statistics are set and retrieved with the :py:meth:`~buildbot.process.buildstep.BuildStep.setStatistic` and :py:meth:`~buildbot.process.buildstep.BuildStep.getStatistic` methods.
The :py:meth:`~buildbot.process.buildstep.BuildStep.hasStatistic` method determines whether a statistic exists.

The Build method :py:meth:`~buildbot.process.build.Build.getSummaryStatistic` can be used to aggregate over all steps in a Build.

BuildStep URLs
~~~~~~~~~~~~~~

Each BuildStep has a collection of `links`.
Each has a name and a target URL.
The web display displays clickable links for each link, making them a useful way to point to extra information about a step.
For example, a step that uploads a build result to an external service might include a link to the uploaded file.

To set one of these links, the :class:`BuildStep` should call the :meth:`~buildbot.process.buildstep.BuildStep.addURL` method with the name of the link and the target URL.
Multiple URLs can be set.
For example::

    @defer.inlineCallbacks
    def run(self):
        ... # create and upload report to coverage server
        url = 'http://coverage.example.com/reports/%s' % reportname
        yield self.addURL('coverage', url)

This also works from log observers, which is helpful for instance if the build output points to an external page such as a detailed log file. The following example parses output of *poudriere*, a tool for building packages on the FreeBSD operating system.

Example output:

.. code-block:: none

    [00:00:00] Creating the reference jail... done
    ...
    [00:00:01] Logs: /usr/local/poudriere/data/logs/bulk/103amd64-2018Q4/2018-10-03_05h47m30s
    ...
    ... build log without details (those are in the above logs directory) ...

Log observer implementation::

    c = BuildmasterConfig = {}
    c['titleURL'] = 'https://my-buildbot.example.com/'
    # ...
    class PoudriereLogLinkObserver(util.LogLineObserver):
        _regex = re.compile(
            r'Logs: /usr/local/poudriere/data/logs/bulk/([-_/0-9A-Za-z]+)$')

        def __init__(self):
            super().__init__()
            self._finished = False

        def outLineReceived(self, line):
            # Short-circuit if URL already found
            if self._finished:
                return

            m = self._regex.search(line.rstrip())
            if m:
                self._finished = True
                # Let's assume local directory /usr/local/poudriere/data/logs/bulk
                # is available as https://my-buildbot.example.com/poudriere/logs
                poudriere_ui_url = c['titleURL'] + 'poudriere/logs/' + m.group(1)
                # Add URLs for build overview page and for per-package log files
                self.step.addURL('Poudriere build web interface', poudriere_ui_url)
                self.step.addURL('Poudriere logs', poudriere_ui_url + '/logs/')

Discovering files
~~~~~~~~~~~~~~~~~

When implementing a :class:`BuildStep` it may be necessary to know about files that are created during the build.
There are a few worker commands that can be used to find files on the worker and test for the existence (and type) of files and directories.

The worker provides the following file-discovery related commands:

* `stat` calls :func:`os.stat` for a file in the worker's build directory.
  This can be used to check if a known file exists and whether it is a regular file, directory or symbolic link.

* `listdir` calls :func:`os.listdir` for a directory on the worker.
  It can be used to obtain a list of files that are present in a directory on the worker.

* `glob` calls :func:`glob.glob` on the worker, with a given shell-style pattern containing wildcards.

For example, we could use stat to check if a given path exists and contains ``*.pyc`` files.
If the path does not exist (or anything fails) we mark the step as failed; if the path exists but is not a directory, we mark the step as having "warnings".

.. code-block:: python


    from buildbot.plugins import steps, util
    from buildbot.interfaces import WorkerTooOldError
    import stat

    class MyBuildStep(steps.BuildStep):

        def __init__(self, dirname, **kwargs):
            super().__init__(**kwargs)
            self.dirname = dirname

        def start(self):
            # make sure the worker knows about stat
            workerver = (self.workerVersion('stat'),
                        self.workerVersion('glob'))
            if not all(workerver):
                raise WorkerTooOldError('need stat and glob')

            cmd = buildstep.RemoteCommand('stat', {'file': self.dirname})

            d = self.runCommand(cmd)
            d.addCallback(lambda res: self.evaluateStat(cmd))
            d.addErrback(self.failed)
            return d

        def evaluateStat(self, cmd):
            if cmd.didFail():
                self.step_status.setText(["File not found."])
                self.finished(util.FAILURE)
                return
            s = cmd.updates["stat"][-1]
            if not stat.S_ISDIR(s[stat.ST_MODE]):
                self.step_status.setText(["'tis not a directory"])
                self.finished(util.WARNINGS)
                return

            cmd = buildstep.RemoteCommand('glob', {'path': self.dirname + '/*.pyc'})

            d = self.runCommand(cmd)
            d.addCallback(lambda res: self.evaluateGlob(cmd))
            d.addErrback(self.failed)
            return d

        def evaluateGlob(self, cmd):
            if cmd.didFail():
                self.step_status.setText(["Glob failed."])
                self.finished(util.FAILURE)
                return
            files = cmd.updates["files"][-1]
            if len(files):
                self.step_status.setText(["Found pycs"]+files)
            else:
                self.step_status.setText(["No pycs found"])
            self.finished(util.SUCCESS)


For more information on the available commands, see :doc:`../developer/master-worker`.

.. todo::

    Step Progress
    BuildStepFailed

.. _buildbot_wsgi_dashboards:

Writing Dashboards with Flask_ or Bottle_
-----------------------------------------

Buildbot Nine UI is written in Javascript.
This allows it to be reactive and real time, but comes at a price of a fair complexity.
Sometimes, you need a dashboard displaying your build results in your own manner but learning AngularJS for that is just too much.

There is a Buildbot plugin which allows to write a server side generated dashboard, and integrate it in the UI.

.. code-block:: python

    # This needs buildbot and buildbot_www >= 0.9.5
    pip install buildbot_wsgi_dashboards flask

- This plugin can use any WSGI compatible web framework, Flask_ is a very common one, Bottle_ is another popular option.

- The application needs to implement a ``/index.html`` route, which will render the html code representing the dashboard.

- The application framework runs in a thread outside of Twisted.
  No need to worry about Twisted and asynchronous code.
  You can use python-requests_ or any library from the python ecosystem to access other servers.

- You could use HTTP in order to access Buildbot :ref:`REST_API`, but you can also use the :ref:`Data_API`, via the provided synchronous wrapper.

    .. py:method:: buildbot_api.dataGet(path, filters=None, fields=None, order=None, limit=None, offset=None):

        :param tuple path: A tuple of path elements representing the API path to fetch.
            Numbers can be passed as strings or integers.
        :param filters: result spec filters
        :param fields: result spec fields
        :param order: result spec order
        :param limit: result spec limit
        :param offset: result spec offset
        :raises: :py:exc:`~buildbot.data.exceptions.InvalidPathError`
        :returns: a resource or list, or None

        This is a blocking wrapper to master.data.get as described in :ref:`Data_API`.
        The available paths are described in the :ref:`REST_API`, as well as the nature of return values depending on the kind of data that is fetched.
        Path can be either the REST path e.g. ``"builders/2/builds/4"`` or tuple e.g. ``("builders", 2, "builds", 4)``.
        The latter form being more convenient if some path parts are coming from variables.
        The :ref:`Data_API` and :ref:`REST_API` are functionally equivalent except:

        - :ref:`Data_API` does not have HTTP connection overhead.
        - :ref:`Data_API` does not enforce authorization rules.

        ``buildbot_api.dataGet`` is accessible via the WSGI application object passed to ``wsgi_dashboards`` plugin (as per the example).

- That html code output of the server runs inside AngularJS application.

  - It will use the CSS of the AngularJS application (including the Bootstrap_ CSS base).
    You can use custom style-sheet with a standard ``style`` tag within your html.
    Custom CSS will be shared with the whole Buildbot application once your dashboard is loaded.
    So you should make sure your custom CSS rules only apply to your dashboard (e.g. by having a specific class for your dashboard's main div)

  - It can use some of the AngularJS directives defined by Buildbot UI (currently only buildsummary is usable).
  - It has full access to the application JS context.

Here is an example of code that you can use in your ``master.cfg`` to create a simple dashboard:



.. literalinclude:: mydashboard.py
   :language: python


Then you need a ``templates/mydashboard.html`` file near your ``master.cfg``.

This template is a standard Jinja_ template which is the default templating engine of Flask_.

.. literalinclude:: mydashboard.html
   :language: guess


.. _Flask: http://flask.pocoo.org/
.. _Bottle: https://bottlepy.org/docs/dev/
.. _Bootstrap: http://getbootstrap.com/css/
.. _Jinja: http://jinja.pocoo.org/
.. _python-requests: http://docs.python-requests.org/en/master/


A Somewhat Whimsical Example (or "It's now customized, how do I deploy it?")
----------------------------------------------------------------------------

Let's say that we've got some snazzy new unit-test framework called Framboozle.
It's the hottest thing since sliced bread.
It slices, it dices, it runs unit tests like there's no tomorrow.
Plus if your unit tests fail, you can use its name for a Web 2.1 startup company, make millions of dollars, and hire engineers to fix the bugs for you, while you spend your afternoons lazily hang-gliding along a scenic pacific beach, blissfully unconcerned about the state of your tests.
[#framboozle_reg]_

To run a Framboozle-enabled test suite, you just run the 'framboozler' command from the top of your source code tree.
The 'framboozler' command emits a bunch of stuff to stdout, but the most interesting bit is that it emits the line "FNURRRGH!" every time it finishes running a test case You'd like to have a test-case counting LogObserver that watches for these lines and counts them, because counting them will help the buildbot more accurately calculate how long the build will take, and this will let you know exactly how long you can sneak out of the office for your hang-gliding lessons without anyone noticing that you're gone.

This will involve writing a new :class:`BuildStep` (probably named "Framboozle") which inherits from :bb:step:`ShellCommand`.
The :class:`BuildStep` class definition itself will look something like this::

    from buildbot.plugins import steps, util

    class FNURRRGHCounter(util.LogLineObserver):
        numTests = 0
        def outLineReceived(self, line):
            if "FNURRRGH!" in line:
                self.numTests += 1
                self.step.setProgress('tests', self.numTests)

    class Framboozle(steps.ShellCommand):
        command = ["framboozler"]

        def __init__(self, **kwargs):
            super().__init__(**kwargs)   # always upcall!
            counter = FNURRRGHCounter()
            self.addLogObserver('stdio', counter)
            self.progressMetrics += ('tests',)

So that's the code that we want to wind up using.
How do we actually deploy it?

You have a number of different options:

.. contents::
   :local:

Inclusion in the :file:`master.cfg` file
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The simplest technique is to simply put the step class definitions in your :file:`master.cfg` file, somewhere before the :class:`BuildFactory` definition where you actually use it in a clause like::

    f = BuildFactory()
    f.addStep(SVN(repourl="stuff"))
    f.addStep(Framboozle())

Remember that :file:`master.cfg` is secretly just a Python program with one job: populating the :data:`BuildmasterConfig` dictionary.
And Python programs are allowed to define as many classes as they like.
So you can define classes and use them in the same file, just as long as the class is defined before some other code tries to use it.

This is easy, and it keeps the point of definition very close to the point of use, and whoever replaces you after that unfortunate hang-gliding accident will appreciate being able to easily figure out what the heck this stupid "Framboozle" step is doing anyways.
The downside is that every time you reload the config file, the Framboozle class will get redefined, which means that the buildmaster will think that you've reconfigured all the Builders that use it, even though nothing changed.
Bleh.

Python file somewhere on the system
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Instead, we can put this code in a separate file, and import it into the master.cfg file just like we would the normal buildsteps like :bb:step:`ShellCommand` and :bb:step:`SVN`.

Create a directory named :file:`~/lib/python`, put the step class definitions in :file:`~/lib/python/framboozle.py`, and run your buildmaster using:

.. code-block:: bash

    PYTHONPATH=~/lib/python buildbot start MASTERDIR

or use the :file:`Makefile.buildbot` to control the way ``buildbot start`` works.
Or add something like this to something like your :file:`~/.bashrc` or :file:`~/.bash_profile` or :file:`~/.cshrc`:

.. code-block:: bash

    export PYTHONPATH=~/lib/python

Once we've done this, our :file:`master.cfg` can look like::

    from framboozle import Framboozle
    f = BuildFactory()
    f.addStep(SVN(repourl="stuff"))
    f.addStep(Framboozle())

or::

    import framboozle
    f = BuildFactory()
    f.addStep(SVN(repourl="stuff"))
    f.addStep(framboozle.Framboozle())

(check out the Python docs for details about how ``import`` and ``from A import B`` work).

What we've done here is to tell Python that every time it handles an "import" statement for some named module, it should look in our :file:`~/lib/python/` for that module before it looks anywhere else.
After our directories, it will try in a bunch of standard directories too (including the one where buildbot is installed).
By setting the :envvar:`PYTHONPATH` environment variable, you can add directories to the front of this search list.

Python knows that once it "import"s a file, it doesn't need to re-import it again.
This means that reconfiguring the buildmaster (with ``buildbot reconfig``, for example) won't make it think the Framboozle class has changed every time, so the Builders that use it will not be spuriously restarted.
On the other hand, you either have to start your buildmaster in a slightly weird way, or you have to modify your environment to set the :envvar:`PYTHONPATH` variable.


Install this code into a standard Python library directory
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Find out what your Python's standard include path is by asking it:

.. code-block:: none

    80:warner@luther% python
    Python 2.4.4c0 (#2, Oct  2 2006, 00:57:46)
    [GCC 4.1.2 20060928 (prerelease) (Debian 4.1.1-15)] on linux2
    Type "help", "copyright", "credits" or "license" for more information.
    >>> import sys
    >>> import pprint
    >>> pprint.pprint(sys.path)
    ['',
     '/usr/lib/python24.zip',
     '/usr/lib/python2.4',
     '/usr/lib/python2.4/plat-linux2',
     '/usr/lib/python2.4/lib-tk',
     '/usr/lib/python2.4/lib-dynload',
     '/usr/local/lib/python2.4/site-packages',
     '/usr/lib/python2.4/site-packages',
     '/usr/lib/python2.4/site-packages/Numeric',
     '/var/lib/python-support/python2.4',
     '/usr/lib/site-python']

In this case, putting the code into :file:`/usr/local/lib/python2.4/site-packages/framboozle.py` would work just fine.
We can use the same :file:`master.cfg` ``import framboozle`` statement as in Option 2.
By putting it in a standard include directory (instead of the decidedly non-standard :file:`~/lib/python`), we don't even have to set :envvar:`PYTHONPATH` to anything special.
The downside is that you probably have to be root to write to one of those standard include directories.

.. _Plugin-Module:

Distribute a Buildbot Plug-In
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

First of all, you must prepare a Python package (if you do not know what that is, please check :doc:`../developer/plugins-publish`, where you can find a couple of pointers to tutorials).

When you have a package, you will have a special file called :file:`setup.py`.
This file needs to be updated to include a pointer to your new step:

.. code-block:: python

    setup(
        ...
        entry_points = {
            ...,
            'buildbot.steps': [
                'Framboozle = framboozle:Framboozle'
            ]
        },
        ...
    )

Where:

* ``buildbot.steps`` is the kind of plugin you offer (more information about possible kinds you can find in :doc:`../developer/plugins-publish`)
* ``framboozle:Framboozle`` consists of two parts: ``framboozle`` is the name of the Python module where to look for ``Framboozle`` class, which implements the plugin
* ``Framboozle`` is the name of the plugin.

  This will allow users of your plugin to use it just like any other Buildbot plugins::

    from buildbot.plugins import steps

    ... steps.Framboozle ...

Now you can upload it to PyPI_ where other people can download it from and use in their build systems.
Once again, the information about how to prepare and upload a package to PyPI_ can be found in tutorials listed in :doc:`../developer/plugins-publish`.

.. _PyPI: http://pypi.python.org/

Submit the code for inclusion in the Buildbot distribution
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Make a fork of buildbot on http://github.com/buildbot/buildbot or post a patch in a bug at http://trac.buildbot.net/.
In either case, post a note about your patch to the mailing list, so others can provide feedback and, eventually, commit it.

When it's committed to the master, the usage is the same as in the previous approach::

    from buildbot.plugins import steps, util

    ...
    f = util.BuildFactory()
    f.addStep(steps.SVN(repourl="stuff"))
    f.addStep(steps.Framboozle())
    ...

And then you don't even have to install :file:`framboozle.py` anywhere on your system, since it will ship with Buildbot.
You don't have to be root, you don't have to set :envvar:`PYTHONPATH`.
But you do have to make a good case for Framboozle being worth going into the main distribution, you'll probably have to provide docs and some unit test cases, you'll need to figure out what kind of beer the author likes (IPA's and Stouts for Dustin), and then you'll have to wait until the next release.
But in some environments, all this is easier than getting root on your buildmaster box, so the tradeoffs may actually be worth it.

Summary
~~~~~~~

Putting the code in master.cfg (1) makes it available to that buildmaster instance.
Putting it in a file in a personal library directory (2) makes it available for any buildmasters you might be running.
Putting it in a file in a system-wide shared library directory (3) makes it available for any buildmasters that anyone on that system might be running.
Getting it into the buildbot's upstream repository (4) makes it available for any buildmasters that anyone in the world might be running.
It's all a matter of how widely you want to deploy that new class.

.. [#framboozle_reg]

   framboozle.com is still available.
   Remember, I get 10% :).
