Release Notes for Buildbot |version|
====================================

..
    Any change that adds a feature or fixes a bug should have an entry here.
    Most simply need an additional bulleted list item, but more significant
    changes can be given a subsection of their own.

The following are the release notes for Buildbot |version|.

Master
------

Features
~~~~~~~~

* :bb:step:`Git` supports an "origin" option to give a name to the remote repo.

* two new general steps are added to handle related builds -- :bb:step:`CancelRelatedBuilds` and :bb:step:`StopRelatedBuilds` -- as well as Gerrit specific ones -- :bb:step:`CancelGerritRelatedBuilds` and :bb:step:`StopGerritRelatedBuilds`.
  More information in :ref:`the manual <handle-related-builds>`.

* :class:`~buildbot.status.github.GitHubStatus` now accepts a ``context`` parameter to be passed to the GitHub Status API.

* :bb:sched:`Triggerable` now accepts a ``reason`` parameter.

Fixes
~~~~~

* Cloning :bb:step:`Git` repository with submodules now works with Git < 1.7.6 instead of failing due to the use of the unsupported ``--force`` option.

Deprecations, Removals, and Non-Compatible Changes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Changes for Developers
~~~~~~~~~~~~~~~~~~~~~~

Slave
-----

Features
~~~~~~~~

* :bb:status:`GerritStatusPush` now has parameter --notify which is used to control e-mail notifications from Gerrit.

* StashStatusPush now accepts optional ``key_format`` and ``name_format`` parameters to configure build reporting to Atlassian Stash.

* Schedulers: the ``codebases`` parameter can now be specified in a simple list-of-strings form

Fixes
~~~~~

Deprecations, Removals, and Non-Compatible Changes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

* Providing Latent AWS EC2 credentails by the .ec2/aws_id file is deprecated:
  Instead, use the standard .aws/credentials file.

Details
-------

For a more detailed description of the changes made in this version, see the git log itself:

.. code-block:: bash

   git log v0.8.12..eight

Older Versions
--------------

Release notes for older versions of Buildbot are available in the :bb:src:`master/docs/relnotes/` directory of the source tree.
Newer versions are also available here:

.. toctree::
    :maxdepth: 1

    0.8.12
    0.8.10
    0.8.9
    0.8.8
    0.8.7
    0.8.6
