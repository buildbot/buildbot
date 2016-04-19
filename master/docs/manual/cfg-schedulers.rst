.. -*- rst -*-
.. _Schedulers:

Schedulers
----------

.. contents::
    :depth: 2
    :local:

Schedulers are responsible for initiating builds on builders.

Some schedulers listen for changes from ChangeSources and generate build sets in response to these changes.
Others generate build sets without changes, based on other events in the buildmaster.

.. _Configuring-Schedulers:

Configuring Schedulers
~~~~~~~~~~~~~~~~~~~~~~

.. bb:cfg:: schedulers

The :bb:cfg:`schedulers` configuration parameter gives a list of scheduler instances, each of which causes builds to be started on a particular set of Builders.
The two basic scheduler classes you are likely to start with are :bb:sched:`SingleBranchScheduler` and :bb:sched:`Periodic`, but you can write a customized subclass to implement more complicated build scheduling.

Scheduler arguments should always be specified by name (as keyword arguments), to allow for future expansion::

    sched = SingleBranchScheduler(name="quick", builderNames=['lin', 'win'])

There are several common arguments for schedulers, although not all are available with all schedulers.

``name``
    Each Scheduler must have a unique name.
    This is used in status displays, and is also available in the build property ``scheduler``.

``builderNames``
    This is the set of builders which this scheduler should trigger, specified as a list of names (strings).

.. index:: Properties; from scheduler

``properties``
    This is a dictionary specifying properties that will be transmitted to all builds started by this scheduler.
    The ``owner`` property may be of particular interest, as its contents (as a list) will be added to the list of "interested users" (:ref:`Doing-Things-With-Users`) for each triggered build.
    For example

    .. code-block:: python

        sched = Scheduler(...,
            properties = {
                'owner': ['zorro@example.com', 'silver@example.com']
            })

``fileIsImportant``
    A callable which takes one argument, a Change instance, and returns ``True`` if the change is worth building, and ``False`` if it is not.
    Unimportant Changes are accumulated until the build is triggered by an important change.
    The default value of None means that all Changes are important.

``change_filter``
    The change filter that will determine which changes are recognized by this scheduler; :ref:`Change-Filters`.
    Note that this is different from ``fileIsImportant``: if the change filter filters out a Change, then it is completely ignored by the scheduler.
    If a Change is allowed by the change filter, but is deemed unimportant, then it will not cause builds to start, but will be remembered and shown in status displays.

``codebases``
    When the scheduler processes data from more than one repository at the same time, a corresponding codebase definition should be passed for each repository.

    This parameter can be specified either as a list of strings (simplest form; use if no special
    overrides are needed) or as a dictionary of dictionaries (where each dict is a codebase definition
    as described next).

    Each codebase definition is a dictionary with any of the keys: ``repository``, ``branch``, ``revision``.
    The codebase definitions are combined in a dictionary keyed by the name of the codebase.

    .. code-block:: python

        codebases = {'codebase1': {'repository':'....',
                                   'branch':'default',
                                   'revision': None},
                     'codebase2': {'repository':'....'} }

    .. important::

       The ``codebases`` parameter is only used to fill in missing details about a codebases when scheduling a build.
       For example, when a change to codebase ``A`` occurs, a scheduler must invent a sourcestamp for codebase ``B``.
       The parameter does not act as a filter on incoming changes -- use a change filter for that purpose.

    Source steps can specify a codebase to which they will apply, and will use the sourcestamp for that codebase.

``onlyImportant``
    A boolean that, when ``True``, only adds important changes to the buildset as specified in the ``fileIsImportant`` callable.
    This means that unimportant changes are ignored the same way a ``change_filter`` filters changes.
    This defaults to ``False`` and only applies when ``fileIsImportant`` is given.

``reason``
    A string that will be used as the reason for the triggered build.

The remaining subsections represent a catalog of the available scheduler types.
All these schedulers are defined in modules under :mod:`buildbot.schedulers`, and the docstrings there are the best source of documentation on the arguments taken by each one.

Scheduler Resiliency
~~~~~~~~~~~~~~~~~~~~

In a multi-master configuration, schedulers with the same name can be configured on multiple masters.
Only one instance of the scheduler will be active.
If that instance becomes inactive, due to its master being shut down or failing, then another instance will become active after a short delay.
This provides resiliency in scheduler configurations, so that schedulers are not a single point of failure in a Buildbot infrastructure.

The Data API and web UI display the master on which each scheduler is running.

There is currently no mechanism to control which master's scheduler instance becomes active.
The behavior is nondeterministic, based on the timing of polling by inactive schedulers.
The failover is non-revertive.

.. _Change-Filters:

Change Filters
~~~~~~~~~~~~~~

Several schedulers perform filtering on an incoming set of changes.
The filter can most generically be specified as a :class:`ChangeFilter`.
Set up a :class:`ChangeFilter` like this::

    from buildbot.plugins import util
    my_filter = util.ChangeFilter(project_re="^baseproduct/.*", branch="devel")

and then add it to a scheduler with the ``change_filter`` parameter::

    sch = SomeSchedulerClass(...,
        change_filter=my_filter)

There are five attributes of changes on which you can filter:

``project``
    the project string, as defined by the ChangeSource.

``repository``
    the repository in which this change occurred.

``branch``
    the branch on which this change occurred.
    Note that 'trunk' or 'master' is often denoted by ``None``.

``category``
    the category, again as defined by the ChangeSource.

``codebase``
    the change's codebase.

For each attribute, the filter can look for a single, specific value::

    my_filter = util.ChangeFilter(project='myproject')

or accept any of a set of values::

    my_filter = util.ChangeFilter(project=['myproject', 'jimsproject'])

or apply a regular expression, using the attribute name with a "``_re``" suffix::

    my_filter = util.ChangeFilter(category_re='.*deve.*')
    # or, to use regular expression flags:
    import re
    my_filter = util.ChangeFilter(category_re=re.compile('.*deve.*', re.I))

For anything more complicated, define a Python function to recognize the strings you want::

    def my_branch_fn(branch):
        return branch in branches_to_build and branch not in branches_to_ignore
    my_filter = util.ChangeFilter(branch_fn=my_branch_fn)

The special argument ``filter_fn`` can be used to specify a function that is given the entire Change object, and returns a boolean.

The entire set of allowed arguments, then, is

+------------+---------------+---------------+
| project    | project_re    | project_fn    |
+------------+---------------+---------------+
| repository | repository_re | repository_fn |
+------------+---------------+---------------+
| branch     | branch_re     | branch_fn     |
+------------+---------------+---------------+
| category   | category_re   | category_fn   |
+------------+---------------+---------------+
| codebase   | codebase_re   | codebase_fn   |
+------------+---------------+---------------+
| filter_fn                                  |
+--------------------------------------------+

A Change passes the filter only if *all* arguments are satisfied.
If no filter object is given to a scheduler, then all changes will be built (subject to any other restrictions the scheduler enforces).

Scheduler Types
~~~~~~~~~~~~~~~

The remaining subsections represent a catalog of the available Scheduler types.
All these Schedulers are defined in modules under :mod:`buildbot.schedulers`, and the docstrings there are the best source of documentation on the arguments taken by each one.

.. bb:sched:: SingleBranchScheduler
.. bb:sched:: Scheduler

.. _Scheduler-SingleBranchScheduler:

SingleBranchScheduler
:::::::::::::::::::::

This is the original and still most popular scheduler class.
It follows exactly one branch, and starts a configurable tree-stable-timer after each change on that branch.
When the timer expires, it starts a build on some set of Builders.
This scheduler accepts a :meth:`fileIsImportant` function which can be used to ignore some Changes if they do not affect any *important* files.

If ``treeStableTimer`` is not set, then this scheduler starts a build for every Change that matches its ``change_filter`` and statsfies :meth:`fileIsImportant`.
If ``treeStableTimer`` is set, then a build is triggered for each set of Changes which arrive within the configured time, and match the filters.

.. note::

   The behavior of this scheduler is undefined, if ``treeStableTimer`` is set, and changes from multiple branches, repositories or codebases are accepted by the filter.

.. note::

   The ``codebases`` argument will filter out codebases not specified there, but *won't* filter based on the branches specified there.

The arguments to this scheduler are:

``name``

``builderNames``

``properties``

``fileIsImportant``

``change_filter``

``onlyImportant``

``reason``

``treeStableTimer``
    The scheduler will wait for this many seconds before starting the build.
    If new changes are made during this interval, the timer will be restarted, so really the build will be started after a change and then after this many seconds of inactivity.

    If ``treeStableTimer`` is ``None``, then a separate build is started immediately for each Change.

``fileIsImportant``
    A callable which takes one argument, a Change instance, and returns ``True`` if the change is worth building, and ``False`` if it is not.
    Unimportant Changes are accumulated until the build is triggered by an important change.
    The default value of None means that all Changes are important.

``categories`` (deprecated; use change_filter)
    A list of categories of changes that this scheduler will respond to.
    If this is specified, then any non-matching changes are ignored.

``branch`` (deprecated; use change_filter)
    The scheduler will pay attention to this branch, ignoring Changes that occur on other branches.
    Setting ``branch`` equal to the special value of ``None`` means it should only pay attention to the default branch.

    .. note::

       ``None`` is a keyword, not a string, so write ``None`` and not ``"None"``.

Example::

    from buildbot.plugins import schedulers, util
    quick = schedulers.SingleBranchScheduler(
                name="quick",
                change_filter=util.ChangeFilter(branch='master'),
                treeStableTimer=60,
                builderNames=["quick-linux", "quick-netbsd"])
    full = schedulers.SingleBranchScheduler(
                name="full",
                change_filter=util.ChangeFilter(branch='master'),
                treeStableTimer=5*60,
                builderNames=["full-linux", "full-netbsd", "full-OSX"])
    c['schedulers'] = [quick, full]

In this example, the two *quick* builders are triggered 60 seconds after the tree has been changed.
The *full* builds do not run quite so quickly (they wait 5 minutes), so hopefully if the quick builds fail due to a missing file or really simple typo, the developer can discover and fix the problem before the full builds are started.
Both schedulers only pay attention to the default branch: any changes on other branches are ignored.
Each scheduler triggers a different set of Builders, referenced by name.

.. note::

   The old names for this scheduler, ``buildbot.scheduler.Scheduler`` and ``buildbot.schedulers.basic.Scheduler``, are deprecated in favor of using :mod:`buildbot.plugins`::

        from buildbot.plugins import schedulers

   However if you must use a fully qualified name, it is ``buildbot.schedulers.basic.SingleBranchScheduler``.

.. bb:sched:: AnyBranchScheduler

.. _AnyBranchScheduler:

AnyBranchScheduler
::::::::::::::::::

This scheduler uses a tree-stable-timer like the default one, but uses a separate timer for each branch.

If ``treeStableTimer`` is not set, then this scheduler is indistinguishable from bb:sched:``SingleBranchScheduler``.
If ``treeStableTimer`` is set, then a build is triggered for each set of Changes which arrive within the configured time, and match the filters.

The arguments to this scheduler are:

``name``

``builderNames``

``properties``

``fileIsImportant``

``change_filter``

``onlyImportant``

``reason``
    See :ref:`Configuring-Schedulers`.

``treeStableTimer``
    The scheduler will wait for this many seconds before starting the build.
    If new changes are made *on the same branch* during this interval, the timer will be restarted.

``branches`` (deprecated; use change_filter)
    Changes on branches not specified on this list will be ignored.

``categories`` (deprecated; use change_filter)
    A list of categories of changes that this scheduler will respond to.
    If this is specified, then any non-matching changes are ignored.

.. bb:sched:: Dependent

.. _Dependent-Scheduler:

Dependent Scheduler
:::::::::::::::::::

It is common to wind up with one kind of build which should only be performed if the same source code was successfully handled by some other kind of build first.
An example might be a packaging step: you might only want to produce .deb or RPM packages from a tree that was known to compile successfully and pass all unit tests.
You could put the packaging step in the same Build as the compile and testing steps, but there might be other reasons to not do this (in particular you might have several Builders worth of compiles/tests, but only wish to do the packaging once).
Another example is if you want to skip the *full* builds after a failing *quick* build of the same source code.
Or, if one Build creates a product (like a compiled library) that is used by some other Builder, you'd want to make sure the consuming Build is run *after* the producing one.

You can use *dependencies* to express this relationship to the Buildbot.
There is a special kind of scheduler named :bb:sched:`Dependent` that will watch an *upstream* scheduler for builds to complete successfully (on all of its Builders).
Each time that happens, the same source code (i.e. the same ``SourceStamp``) will be used to start a new set of builds, on a different set of Builders.
This *downstream* scheduler doesn't pay attention to Changes at all.
It only pays attention to the upstream scheduler.

If the build fails on any of the Builders in the upstream set, the downstream builds will not fire.
Note that, for SourceStamps generated by a :bb:sched:`Dependent` scheduler, the ``revision`` is ``None``, meaning HEAD.
If any changes are committed between the time the upstream scheduler begins its build and the time the dependent scheduler begins its build, then those changes will be included in the downstream build.
See the :bb:sched:`Triggerable` scheduler for a more flexible dependency mechanism that can avoid this problem.

The keyword arguments to this scheduler are:

``name``

``builderNames``

``properties``
    See :ref:`Configuring-Schedulers`.

``upstream``
    The upstream scheduler to watch.
    Note that this is an *instance*, not the name of the scheduler.

Example::

    from buildbot.plugins import schedulers
    tests = schedulers.SingleBranchScheduler(name="just-tests",
                                             treeStableTimer=5*60,
                                             builderNames=["full-linux",
                                                           "full-netbsd",
                                                           "full-OSX"])
    package = schedulers.Dependent(name="build-package",
                                   upstream=tests, # <- no quotes!
                                   builderNames=["make-tarball", "make-deb",
                                                 "make-rpm"])
    c['schedulers'] = [tests, package]

.. bb:sched:: Periodic

.. _Periodic-Scheduler:

Periodic Scheduler
::::::::::::::::::

This simple scheduler just triggers a build every *N* seconds.

The arguments to this scheduler are:

``name``

``builderNames``

``properties``

``onlyImportant``

``createAbsoluteSourceStamps``
    This option only has effect when using multiple codebases.
    When ``True``, it uses the last seen revision for each codebase that does not have a change.
    When ``False``, the default value, codebases without changes will use the revision from the ``codebases`` argument.

``onlyIfChanged``
    If this is true, then builds will not be scheduled at the designated time
    *unless* the specified branch has seen an important change since
    the previous build.

``reason``
    See :ref:`Configuring-Schedulers`.

``periodicBuildTimer``
    The time, in seconds, after which to start a build.

Example::

    from buildbot.plugins import schedulers
    nightly = schedulers.Periodic(name="daily",
                                  builderNames=["full-solaris"],
                                  periodicBuildTimer=24*60*60)
    c['schedulers'] = [nightly]

The scheduler in this example just runs the full solaris build once per day.
Note that this scheduler only lets you control the time between builds, not the absolute time-of-day of each Build, so this could easily wind up an *evening* or *every afternoon* scheduler depending upon when it was first activated.

.. bb:sched:: Nightly

.. _Nightly-Scheduler:

Nightly Scheduler
:::::::::::::::::

This is highly configurable periodic build scheduler, which triggers a build at particular times of day, week, month, or year.
The configuration syntax is very similar to the well-known ``crontab`` format, in which you provide values for minute, hour, day, and month (some of which can be wildcards), and a build is triggered whenever the current time matches the given constraints.
This can run a build every night, every morning, every weekend, alternate Thursdays, on your boss's birthday, etc.

Pass some subset of ``minute``, ``hour``, ``dayOfMonth``, ``month``, and ``dayOfWeek``\; each may be a single number or a list of valid values.
The builds will be triggered whenever the current time matches these values.
Wildcards are represented by a '*' string.
All fields default to a wildcard except 'minute', so with no fields this defaults to a build every hour, on the hour.
The full list of parameters is:

``name``

``builderNames``

``properties``

``fileIsImportant``

``change_filter``

``onlyImportant``

``reason``

``codebases``

``createAbsoluteSourceStamps``
    This option only has effect when using multiple codebases.
    When ``True``, it uses the last seen revision for each codebase that does not have a change.
    When ``False``, the default value, codebases without changes will use the revision from the ``codebases`` argument.

``onlyIfChanged``
    If this is true, then builds will not be scheduled at the designated time *unless* the change filter has accepted an important change since the previous build.

``branch``
    (deprecated; use ``change_filter`` and ``codebases``)
    The branch to build when the time comes, and the branch to filter for if ``change_filter`` is not specified.
    Remember that a value of ``None`` here means the default branch, and will not match other branches!

``minute``
    The minute of the hour on which to start the build.
    This defaults to 0, meaning an hourly build.

``hour``
    The hour of the day on which to start the build, in 24-hour notation.
    This defaults to \*, meaning every hour.

``dayOfMonth``
    The day of the month to start a build.
    This defaults to ``*``, meaning every day.

``month``
    The month in which to start the build, with January = 1.
    This defaults to ``*``, meaning every month.

``dayOfWeek``
    The day of the week to start a build, with Monday = 0.
    This defaults to ``*``, meaning every day of the week.

For example, the following :file:`master.cfg` clause will cause a build to be started every night at 3:00am::

    from buildbot.plugins import schedulers
    c['schedulers'].append(
        schedulers.Nightly(name='nightly',
                           branch='master',
                           builderNames=['builder1', 'builder2'],
                           hour=3, minute=0))

This scheduler will perform a build each Monday morning at 6:23am and again at 8:23am, but only if someone has committed code in the interim::

    c['schedulers'].append(
        schedulers.Nightly(name='BeforeWork',
                           branch=`default`,
                           builderNames=['builder1'],
                           dayOfWeek=0, hour=[6,8], minute=23,
                           onlyIfChanged=True))

The following runs a build every two hours, using Python's :func:`range` function::

    c.schedulers.append(
        timed.Nightly(name='every2hours',
            branch=None, # default branch
            builderNames=['builder1'],
            hour=range(0, 24, 2)))

Finally, this example will run only on December 24th::

    c['schedulers'].append(
        timed.Nightly(name='SleighPreflightCheck',
            branch=None, # default branch
            builderNames=['flying_circuits', 'radar'],
            month=12,
            dayOfMonth=24,
            hour=12,
            minute=0))

.. bb:sched:: Try_Jobdir
.. bb:sched:: Try_Userpass

.. _Try-Schedulers:

Try Schedulers
::::::::::::::

This scheduler allows developers to use the :command:`buildbot try` command to trigger builds of code they have not yet committed.
See :bb:cmdline:`try` for complete details.

Two implementations are available: :bb:sched:`Try_Jobdir` and :bb:sched:`Try_Userpass`.
The former monitors a job directory, specified by the ``jobdir`` parameter, while the latter listens for PB connections on a specific ``port``, and authenticates against ``userport``.

The buildmaster must have a scheduler instance in the config file's :bb:cfg:`schedulers` list to receive try requests.
This lets the administrator control who may initiate these `trial` builds, which branches are eligible for trial builds, and which Builders should be used for them.

The scheduler has various means to accept build requests.
All of them enforce more security than the usual buildmaster ports do.
Any source code being built can be used to compromise the worker accounts, but in general that code must be checked out from the VC repository first, so only people with commit privileges can get control of the workers.
The usual force-build control channels can waste worker time but do not allow arbitrary commands to be executed by people who don't have those commit privileges.
However, the source code patch that is provided with the trial build does not have to go through the VC system first, so it is important to make sure these builds cannot be abused by a non-committer to acquire as much control over the workers as a committer has.
Ideally, only developers who have commit access to the VC repository would be able to start trial builds, but unfortunately the buildmaster does not, in general, have access to VC system's user list.

As a result, the try scheduler requires a bit more configuration.
There are currently two ways to set this up:

``jobdir`` (ssh)
    This approach creates a command queue directory, called the :file:`jobdir`, in the buildmaster's working directory.
    The buildmaster admin sets the ownership and permissions of this directory to only grant write access to the desired set of developers, all of whom must have accounts on the machine.
    The :command:`buildbot try` command creates a special file containing the source stamp information and drops it in the jobdir, just like a standard maildir.
    When the buildmaster notices the new file, it unpacks the information inside and starts the builds.

    The config file entries used by 'buildbot try' either specify a local queuedir (for which write and mv are used) or a remote one (using scp and ssh).

    The advantage of this scheme is that it is quite secure, the disadvantage is that it requires fiddling outside the buildmaster config (to set the permissions on the jobdir correctly).
    If the buildmaster machine happens to also house the VC repository, then it can be fairly easy to keep the VC userlist in sync with the trial-build userlist.
    If they are on different machines, this will be much more of a hassle.
    It may also involve granting developer accounts on a machine that would not otherwise require them.

    To implement this, the worker invokes :samp:`ssh -l {username} {host} buildbot tryserver {ARGS}`, passing the patch contents over stdin.
    The arguments must include the inlet directory and the revision information.

``user+password`` (PB)
    In this approach, each developer gets a username/password pair, which are all listed in the buildmaster's configuration file.
    When the developer runs :command:`buildbot try`, their machine connects to the buildmaster via PB and authenticates themselves using that username and password, then sends a PB command to start the trial build.

    The advantage of this scheme is that the entire configuration is performed inside the buildmaster's config file.
    The disadvantages are that it is less secure (while the `cred` authentication system does not expose the password in plaintext over the wire, it does not offer most of the other security properties that SSH does).
    In addition, the buildmaster admin is responsible for maintaining the username/password list, adding and deleting entries as developers come and go.

For example, to set up the `jobdir` style of trial build, using a command queue directory of :file:`{MASTERDIR}/jobdir` (and assuming that all your project developers were members of the ``developers`` unix group), you would first set up that directory:

.. code-block:: bash

    mkdir -p MASTERDIR/jobdir MASTERDIR/jobdir/new MASTERDIR/jobdir/cur MASTERDIR/jobdir/tmp
    chgrp developers MASTERDIR/jobdir MASTERDIR/jobdir/*
    chmod g+rwx,o-rwx MASTERDIR/jobdir MASTERDIR/jobdir/*

and then use the following scheduler in the buildmaster's config file::

    from buildbot.plugins import schedulers
    s = schedulers.Try_Jobdir(name="try1",
                              builderNames=["full-linux", "full-netbsd",
                                            "full-OSX"],
                              jobdir="jobdir")
    c['schedulers'] = [s]

Note that you must create the jobdir before telling the buildmaster to use this configuration, otherwise you will get an error.
Also remember that the buildmaster must be able to read and write to the jobdir as well.
Be sure to watch the :file:`twistd.log` file (:ref:`Logfiles`) as you start using the jobdir, to make sure the buildmaster is happy with it.

.. note::

   Patches in the jobdir are encoded using netstrings, which place an arbitrary upper limit on patch size of 99999 bytes.
   If your submitted try jobs are rejected with `BadJobfile`, try increasing this limit with a snippet like this in your `master.cfg`::

        from twisted.protocols.basic import NetstringReceiver
        NetstringReceiver.MAX_LENGTH = 1000000

To use the username/password form of authentication, create a :class:`Try_Userpass` instance instead.
It takes the same ``builderNames`` argument as the :class:`Try_Jobdir` form, but accepts an additional ``port`` argument (to specify the TCP port to listen on) and a ``userpass`` list of username/password pairs to accept.
Remember to use good passwords for this: the security of the worker accounts depends upon it::

    from buildbot.plugins import schedulers
    s = schedulers.Try_Userpass(name="try2",
                                builderNames=["full-linux", "full-netbsd",
                                              "full-OSX"],
                                port=8031,
                                userpass=[("alice","pw1"), ("bob", "pw2")])
    c['schedulers'] = [s]

Like most places in the buildbot, the ``port`` argument takes a `strports` specification.
See :mod:`twisted.application.strports` for details.

.. bb:sched:: Triggerable

.. index:: Triggers

.. _Triggerable-Scheduler:

Triggerable Scheduler
:::::::::::::::::::::

The :bb:sched:`Triggerable` scheduler waits to be triggered by a :bb:step:`Trigger` step (see :ref:`Triggering-Schedulers`) in another build.
That step can optionally wait for the scheduler's builds to complete.
This provides two advantages over :bb:sched:`Dependent` schedulers.
First, the same scheduler can be triggered from multiple builds.
Second, the ability to wait for :bb:sched:`Triggerable`'s builds to complete provides a form of "subroutine call", where one or more builds can "call" a scheduler to perform some work for them, perhaps on other workers.
The :bb:sched:`Triggerable` scheduler supports multiple codebases.
The scheduler filters out all codebases from :bb:step:`Trigger` steps that are not configured in the scheduler.

The parameters are just the basics:

``name``

``builderNames``

``properties``

``reason``

``codebases``
    See :ref:`Configuring-Schedulers`.

This class is only useful in conjunction with the :bb:step:`Trigger` step.
Here is a fully-worked example::

    from buildbot.plugins import schedulers, util, steps

    checkin = schedulers.SingleBranchScheduler(name="checkin",
                                               branch=None,
                                               treeStableTimer=5*60,
                                               builderNames=["checkin"])
    nightly = schedulers.Nightly(name='nightly',
                                 branch=None,
                                 builderNames=['nightly'],
                                 hour=3, minute=0)

    mktarball = schedulers.Triggerable(name="mktarball", builderNames=["mktarball"])
    build = schedulers.Triggerable(name="build-all-platforms",
                                   builderNames=["build-all-platforms"])
    test = schedulers.Triggerable(name="distributed-test",
                                  builderNames=["distributed-test"])
    package = schedulers.Triggerable(name="package-all-platforms",
                                     builderNames=["package-all-platforms"])
    c['schedulers'] = [mktarball, checkin, nightly, build, test, package]

    # on checkin, make a tarball, build it, and test it
    checkin_factory = util.BuildFactory()
    checkin_factory.addStep(steps.Trigger(schedulerNames=['mktarball'],
                                          waitForFinish=True))
    checkin_factory.addStep(steps.Trigger(schedulerNames=['build-all-platforms'],
                                          waitForFinish=True))
    checkin_factory.addStep(steps.Trigger(schedulerNames=['distributed-test'],
                                          waitForFinish=True))

    # and every night, make a tarball, build it, and package it
    nightly_factory = util.BuildFactory()
    nightly_factory.addStep(steps.Trigger(schedulerNames=['mktarball'],
                                          waitForFinish=True))
    nightly_factory.addStep(steps.Trigger(schedulerNames=['build-all-platforms'],
                                          waitForFinish=True))
    nightly_factory.addStep(steps.Trigger(schedulerNames=['package-all-platforms'],
                                          waitForFinish=True))

.. bb:sched:: NightlyTriggerable

NightlyTriggerable Scheduler
::::::::::::::::::::::::::::

.. py:class:: buildbot.schedulers.timed.NightlyTriggerable

The :bb:sched:`NightlyTriggerable` scheduler is a mix of the :bb:sched:`Nightly` and :bb:sched:`Triggerable` schedulers.
This scheduler triggers builds at a particular time of day, week, or year, exactly as the :bb:sched:`Nightly` scheduler.
However, the source stamp set that is used that provided by the last :bb:step:`Trigger` step that targeted this scheduler.

The parameters are just the basics:

``name``

``builderNames``

``properties``

``codebases``
    See :ref:`Configuring-Schedulers`.

``minute``

``hour``

``dayOfMonth``

``month``

``dayOfWeek``
    See :bb:sched:`Nightly`.

This class is only useful in conjunction with the :bb:step:`Trigger` step.
Note that ``waitForFinish`` is ignored by :bb:step:`Trigger` steps targeting this scheduler.

Here is a fully-worked example::

    from buildbot.plugins import schedulers, util, steps

    checkin = schedulers.SingleBranchScheduler(name="checkin",
                                               branch=None,
                                               treeStableTimer=5*60,
                                               builderNames=["checkin"])
    nightly = schedulers.NightlyTriggerable(name='nightly',
                                            builderNames=['nightly'],
                                            hour=3, minute=0)
    c['schedulers'] = [checkin, nightly]

    # on checkin, run tests
    checkin_factory = util.BuildFactory([
        steps.Test(),
        steps.Trigger(schedulerNames=['nightly'])
    ])

    # and every night, package the latest successful build
    nightly_factory = util.BuildFactory([
        steps.ShellCommand(command=['make', 'package'])
    ])

.. bb:sched:: ForceScheduler

.. index:: Forced Builds

ForceScheduler Scheduler
::::::::::::::::::::::::

The :bb:sched:`ForceScheduler` scheduler is the way you can configure a force build form in the web UI.

In the ``/#/builders/:builderid`` web page, you will see, on the top right of the page, one button for each :bb:sched:`ForceScheduler` scheduler that was configured for this builder.
If you click on that button, a dialog will let you choose various parameters for requesting a new build.

The Buildbot framework allows you to customize exactly how the build form looks, which builders have a force build form (it might not make sense to force build every builder), and who is allowed to force builds on which builders.

How you do so is by configuring a :bb:sched:`ForceScheduler`, and add it into the list :bb:cfg:`schedulers`.

The scheduler takes the following parameters:

``name``

    Name of the scheduler (should be an :ref:`Identifier <type-identifier>`).

``builderNames``

    List of builders where the force button should appear.
    See :ref:`Configuring-Schedulers`.

``reason``

    A :ref:`parameter <ForceScheduler-Parameters>` allowing the user to specify the reason for the build.
    The default value is a string parameter with a default value "force build".

``reasonString``

    A string that will be used to create the build reason for the forced build.
    This string can contain the placeholders ``%(owner)s`` and ``%(reason)s``, which represents the value typed into the reason field.

``username``

    A :ref:`parameter <ForceScheduler-Parameters>` specifying the username associated with the build (aka owner).
    The default value is a username parameter.

``codebases``

    A list of strings or :ref:`CodebaseParameter <ForceScheduler-Parameters>` specifying the codebases that should be presented.
    The default is a single codebase with no name (i.e. `codebases=['']`).

``properties``

    A list of :ref:`parameters <ForceScheduler-Parameters>`, one for each property.
    These can be arbitrary parameters, where the parameter's name is taken as the property name, or ``AnyPropertyParameter``, which allows the web user to specify the property name.
    The default value is an empty list.

``buttonName``

    The name of the "submit" button on the resulting force-build form.
    This defaults to the name of scheduler.

An example may be better than long explanation.
What you need in your config file is something like::

    from buildbot.plugins import schedulers, util

    sch = schedulers.ForceScheduler(
        name="force",
        buttonName="pushMe!",
        label="My nice Force form",
        builderNames=["my-builder"],

        codebases=[
            util.CodebaseParameter(
                "",
                name="Main repository",
                # will generate a combo box
                branch=util.ChoiceStringParameter(
                    name="branch",
                    choices=["master", "hest"],
                    default="master"),

                # will generate nothing in the form, but revision, repository,
                # and project are needed by buildbot scheduling system so we
                # need to pass a value ("")
                revision=util.FixedParameter(name="revision", default=""),
                repository=util.FixedParameter(name="repository", default=""),
                project=util.FixedParameter(name="project", default=""),
            ),
        ],

        # will generate a text input
        reason=util.StringParameter(name="reason",
                                    label="reason:",
                                    required=True, size=80),

        # in case you dont require authentication this will display
        # input for user to type his name
        username=util.UserNameParameter(label="your name:",
                                        size=80),
        # A completely customized property list.  The name of the
        # property is the name of the parameter
        properties=[
            util.NestedParameter(name="options", label="Build Options", layout="vertical", fields=[
                util.StringParameter(name="pull_url",
                                     label="optionally give a public Git pull url:",
                                     default="", size=80),
                util.BooleanParameter(name="force_build_clean",
                                      label="force a make clean",
                                      default=False)
            ])
        ])

This will result in the following UI:

.. image:: _images/forcedialog1.png
   :alt: Force Form Result


Authorization
.............

The force scheduler uses the web interface's authorization framework to determine which user has the right to force which build.
Here is an example of code on how you can define which user has which right::

    user_mapping = {
        re.compile("project1-builder"): ["project1-maintainer", "john"] ,
        re.compile("project2-builder"): ["project2-maintainer", "jack"],
        re.compile(".*"): ["root"]
    }
    def force_auth(user,  status):
        global user_mapping
        for r,users in user_mapping.items():
            if r.match(status.name):
                if user in users:
                        return True
        return False

    # use authz_cfg in your WebStatus setup
    authz_cfg=authz.Authz(
        auth=my_auth,
        forceBuild = force_auth,
    )

.. _ForceScheduler-Parameters:

ForceScheduler Parameters
.........................

Most of the arguments to :bb:sched:`ForceScheduler` are "parameters".
Several classes of parameters are available, each describing a different kind of input from a force-build form.

All parameter types have a few common arguments:

``name`` (required)

    The name of the parameter.
    For properties, this will correspond to the name of the property that your parameter will set.
    The name is also used internally as the identifier for in the HTML form.

``label`` (optional; default is same as name)

    The label of the parameter.
    This is what is displayed to the user.

``tablabel`` (optional; default is same as label)

    The label of the tab if this parameter is included into a tab layout NestedParameter.
    This is what is displayed to the user.

``default`` (optional; default: "")

    The default value for the parameter, that is used if there is no user input.

``required`` (optional; default: False)

    If this is true, then an error will be shown to user if there is no input in this field

The parameter types are:

NestedParameter
###############

::

    NestedParameter(name="options", label="Build options" layout="vertical", fields=[...]),

This parameter type is a special parameter which contains other parameters.
This can be used to group a set of parameters together, and define the layout of your form.
You can recursively include NestedParameter into NestedParameter, to build very complex UI.

It adds the following arguments:

``layout`` (optional, default: "vertical")

    The layout defines how the fields are placed in the form.

    The layouts implemented in the standard web application are:

    * ``simple``: fields are displayed one by one without alignment.
        They take the horizontal space that they need.

    * ``vertical``: all fields are displayed vertically, aligned in columns (as per the ``column`` attribute of the NestedParameter)

    * ``tabs``: Each field gets its own `tab <http://getbootstrap.com/components/#nav-tabs>`_.
        This can be used to declare complex build forms which won't fit into one screen.
        The children fields are usually other NestedParameters with vertical layout.

``columns`` (optional, accepted values are 1,2,3,4)

    The number of columns to use for a `vertical` layout.
    If omitted, it is set to 1 unless there are more than 3 visible child fields in which case it is set to 2.

FixedParameter
##############

::

    FixedParameter(name="branch", default="trunk"),

This parameter type will not be shown on the web form, and always generate a property with its default value.

StringParameter
###############

::

    StringParameter(name="pull_url",
        label="optionally give a public Git pull url:",
        default="", size=80)

This parameter type will show a single-line text-entry box, and allow the user to enter an arbitrary string.
It adds the following arguments:

``regex`` (optional)

    A string that will be compiled as a regex, and used to validate the input of this parameter.

``size`` (optional; default: 10)

    The width of the input field (in characters).

TextParameter
#############

::

    StringParameter(name="comments",
        label="comments to be displayed to the user of the built binary",
        default="This is a development build", cols=60, rows=5)

This parameter type is similar to StringParameter, except that it is represented in the HTML form as a ``textarea``, allowing multi-line input.
It adds the StringParameter arguments, this type allows:

``cols`` (optional; default: 80)

    The number of columns the ``textarea`` will have.

``rows`` (optional; default: 20)

    The number of rows the ``textarea`` will have

This class could be subclassed in order to have more customization e.g.

* developer could send a list of Git branches to pull from
* developer could send a list of gerrit changes to cherry-pick,
* developer could send a shell script to amend the build.

Beware of security issues anyway.

IntParameter
############

::

    IntParameter(name="debug_level",
        label="debug level (1-10)", default=2)

This parameter type accepts an integer value using a text-entry box.

BooleanParameter
################

::

    BooleanParameter(name="force_build_clean",
        label="force a make clean", default=False)

This type represents a boolean value.
It will be presented as a checkbox.

UserNameParameter
#################

::

    UserNameParameter(label="your name:", size=80)

This parameter type accepts a username.
If authentication is active, it will use the authenticated user instead of displaying a text-entry box.

``size`` (optional; default: 10)
    The width of the input field (in characters).

``need_email`` (optional; default True)
    If true, require a full email address rather than arbitrary text.

.. bb:sched:: ChoiceStringParameter

ChoiceStringParameter
#####################

::

    ChoiceStringParameter(name="branch",
        choices=["main","devel"], default="main")

This parameter type lets the user choose between several choices (e.g the list of branches you are supporting, or the test campaign to run).
If ``multiple`` is false, then its result is a string - one of the choices.
If ``multiple`` is true, then the result is a list of strings from the choices.

Note that for some use cases, the choices need to be generated dynamically.
This can be done via subclassing and overriding the 'getChoices' member function.
An example of this is provided by the source for the :py:class:`InheritBuildParameter` class.

Its arguments, in addition to the common options, are:

``choices``

    The list of available choices.

``strict`` (optional; default: True)

    If true, verify that the user's input is from the list.
    Note that this only affects the validation of the form request; even if this argument is False, there is no HTML form component available to enter an arbitrary value.

``multiple``

    If true, then the user may select multiple choices.

Example::

        ChoiceStringParameter(name="forced_tests",
                              label="smoke test campaign to run",
                              default=default_tests,
                              multiple=True,
                              strict=True,
                              choices=["test_builder1", "test_builder2",
                                       "test_builder3"])

        # .. and later base the schedulers to trigger off this property:

        # triggers the tests depending on the property forced_test
        builder1.factory.addStep(Trigger(name="Trigger tests",
                                        schedulerNames=Property("forced_tests")))

CodebaseParameter
#################

::

    CodebaseParameter(codebase="myrepo")

This is a parameter group to specify a sourcestamp for a given codebase.

``codebase``

    The name of the codebase.

``branch`` (optional; default: StringParameter)

    A :ref:`parameter <ForceScheduler-Parameters>` specifying the branch to build.
    The default value is a string parameter.

``revision`` (optional; default: StringParameter)

    A :ref:`parameter <ForceScheduler-Parameters>` specifying the revision to build.
    The default value is a string parameter.

``repository`` (optional; default: StringParameter)

    A :ref:`parameter <ForceScheduler-Parameters>` specifying the repository for the build.
    The default value is a string parameter.

``project`` (optional; default: StringParameter)

    A :ref:`parameter <ForceScheduler-Parameters>` specifying the project for the build.
    The default value is a string parameter.

.. bb:sched:: InheritBuildParameter

InheritBuildParameter
#####################

.. note::

    InheritBuildParameter is not yet ported to data API, and cannot be used with buildbot nine yet(:bug:`3521`).

This is a special parameter for inheriting force build properties from another build.
The user is presented with a list of compatible builds from which to choose, and all forced-build parameters from the selected build are copied into the new build.
The new parameter is:

``compatible_builds``

   A function to find compatible builds in the build history.
   This function is given the master :py:class:`~buildbot.status.master.Status` instance as first argument, and the current builder name as second argument, or None when forcing all builds.

Example::

    def get_compatible_builds(status, builder):
        if builder is None: # this is the case for force_build_all
            return ["cannot generate build list here"]
        # find all successful builds in builder1 and builder2
        builds = []
        for builder in ["builder1","builder2"]:
            builder_status = status.getBuilder(builder)
            for num in xrange(1,40): # 40 last builds
                b = builder_status.getBuild(-num)
                if not b:
                    continue
                if b.getResults() == FAILURE:
                    continue
                builds.append(builder+"/"+str(b.getNumber()))
        return builds

    # ...

    sched = Scheduler(...,
        properties=[
            InheritBuildParameter(
                name="inherit",
                label="promote a build for merge",
                compatible_builds=get_compatible_builds,
                required = True),
                ])

.. bb:sched:: WorkerChoiceParameter

WorkerChoiceParameter
#####################

.. note::

    WorkerChoiceParameter is not yet ported to data API, and cannot be used with buildbot nine yet(:bug:`3521`).

This parameter allows a scheduler to require that a build is assigned to the chosen worker.
The choice is assigned to the `workername` property for the build.
The :py:class:`~buildbot.builder.enforceChosenWorker` functor must be assigned to the ``canStartBuild`` parameter for the ``Builder``.

Example::

    from buildbot.plugins import util

    # schedulers:
    ForceScheduler(
        # ...
        properties=[
            WorkerChoiceParameter(),
        ]
    )

    # builders:
    BuilderConfig(
        # ...
        canStartBuild=util.enforceChosenWorker,
    )

AnyPropertyParameter
####################

This parameter type can only be used in ``properties``, and allows the user to specify both the property name and value in the web form.

This Parameter is here to reimplement old Buildbot behavior, and should be avoided.
Stricter parameter name and type should be preferred.
