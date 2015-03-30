================
Subversion Guide
================

`Apache Subversion <https://subversion.apache.org/>`_ is one of the version control systems that is quite popular in both open sources world as well as in enterprise setting.
Since there are different ways Subversion can be used, we cover the most popular approaches in this guide:

.. contents::
   :local:
   :depth: 2

Following Trunk
===============

Let's assume you have a Subversion repository that keeps history of one project only, it is accessible as ``http://example.org/svn`` and you use the `standard layout <http://svnbook.red-bean.com/en/1.7/svn.branchmerge.maint.html#svn.branchmerge.maint.layout>`_ in your repository:

.. code-block:: none

    /
        trunk/
        branches/
        tags/

Let's also assume that your project uses :command:`make`, running ``make`` builds the program and running ``make test`` executes the tests.
Then the following config (only relevant bits are shown) would allow you to check that every commit you make in the ``trunk`` still compiles and all test cases pass.

.. code-block:: python

    # master.cfg

    from buildbot.plugins import buildslave, changes, schedulers, steps

    c = BuildmasterConfig = {}

    ...

    c['slaves'] = [
        buildslave.BuildSlave("slave", "pass")  # These are something you'd like to change
    ]

    ...

    c['change_source'].append(
        changes.SVNPoller(
            svnurl='http://example.org/svn/trunk',  # Location to watch
            pollInterval=600)                       # How often to check for new changes, secs
    )

    ...

    c['schedulers'].append(
        schedulers.SingleBranchScheduler(
            name="basic",
            branch=None,                # The convention is that 'trunk' is represented by 'None` value
            treeStableTimer=None,       # We want to build every change
            builderNames=["basic"]),    # This is the builder to use
    )

    ...

    factory = util.BuildFactory([
        steps.SVN(
            repourl='http://example.org/svn/trunk',     # This is where the code is
            mode='incremental'),                        # Do not remove previously built artifacts
        steps.Compile(),                                # Perform 'make' to build the code
        steps.Test()                                    # Perform 'make tests' to test the built code
    ])

    c['builders'].append(
        util.BuilderConfig(
            name="basic",               # This is the builder that we mentioned above
            slavenames=["slave"],       # Use this buildslave to actually build
            factory=factory)            # These are the steps that need to be performed
    )

    ...

Following a Branch
==================

Provided that you work with the same repository as you did in the previous section, you now want to follow changes in ``branches/feature``.
All you need to update in :file:`master.cfg` are the following lines:

.. code-block:: python
    :emphasize-lines: 5, 13

    ...

    c['change_source'].append(
        changes.SVNPoller(
            svnurl='http://example.org/svn/branches/feature',   # Location to watch
            pollInterval=600)                                   # How often to check for new changes, secs
    )

    ...

    factory = util.BuildFactory([
        steps.SVN(
            repourl='http://example.org/svn/branches/feature',  # This is where the code is
            mode='incremental'),                                # Do not remove previously built artifacts
        steps.Compile(),                                        # Perform 'make' to build the code
        steps.Test()                                            # Perform 'make tests' to test the built code
    ])

    ...

This is pretty common to specify the same URL for :class:`SVNPoller` change source as well as for :class:`SVN` build step and it's very easy to make a mistake to update only one of them.
Since :file:`master.cfg` is a Python script, you can avoid making this kind of mistakes by adding a global variable:

.. code-block:: python
    :emphasize-lines: 3, 9, 17

    ...

    _SVN_URL = 'http://example.org/svn/branches/feature'    # URL to work with

    ...

    c['change_source'].append(
        changes.SVNPoller(
            svnurl=_SVN_URL,    # Location to watch
            pollInterval=600)   # How often to check for new changes, secs
    )

    ...

    factory = util.BuildFactory([
        steps.SVN(
            repourl=_SVN_URL,       # This is where the code is
            mode='incremental'),    # Do not remove previously built artifacts
        steps.Compile(),            # Perform 'make' to build the code
        steps.Test()                # Perform 'make tests' to test the built code
    ])

    ...

At this point you might start to wonder, why the ``branch`` parameter was not changed in

.. code-block:: python
    :emphasize-lines: 4

    c['schedulers'].append(
        schedulers.SingleBranchScheduler(
            name="basic",
            branch=None,                # The convention is that 'trunk' is represented by 'None` value
            treeStableTimer=None,       # We want to build every change
            builderNames=["basic"]),    # This is the builder to use
    )

Following Trunk And a Branch
============================

Following Several Projects
==========================

Following Independent Projects
------------------------------

Following Project Groups
------------------------
