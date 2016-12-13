Release Notes
~~~~~~~~~~~~~
..
    Don't write to this file anymore!!

    Buildbot now uses towncrier to manage its release notes.
    towncrier helps to avoid the need for rebase when several people work at the same time on the releasenote files.

    Each PR should come with a file in the master/buildbot/newsfragment directory

.. towncrier release notes start

Buildbot ``0.9.2`` ( ``2016-12-13`` )
===================================================

Bug fixes
---------

- Fix :py:class:`~buildbot.www.oauth2.GitHubAuth` to retrieve all organizations
  instead of only those publicly available.
- Fixed `ref` to point to `branch` instead of commit `sha` in
  :py:class:`~buildbot.reporters.GitlabStatusPush`
- :bb:reporter:`IRC` :py:meth:`maybeColorize` is able to highlight single words
  and stop colorization at the end. The previous implementation only stopped
  colorization but not boldface.
- fix compatibility issue with mysql5 (do not set default value for TEXT
  column).
- Fixed `addChange` in :py:class:`~buildbot.data.changes.Change` to use the
  `revlink` configuration option to generate the revlink.
- fix threading issue in
  :py:class:`~buildbot.plugins.worker.DockerLatentWorker`

Features
--------

- Implement :py:class:`~buildbot.www.oauth2.BitbucketAuth`.
- New :bb:chsrc:`GerritEventLogPoller` poller to poll Gerrit changes via http
  API.
- New :bb:reporter:`GerritVerifyStatusPush` can send multiple review status for
  the same Gerrit change.
- :bb:reporter:`IRC` appends the builder URL to a successful/failed build if
  available
- :bb:reporter:`MailNotifier` now accepts ``useSmtps`` parameter for initiating
  connection over an SSL/TLS encrypted connection (SMTPS)
- New support for ``Mesos`` and `Marathon
  <https://mesosphere.github.io/marathon/>`_ via
  :py:class:`~buildbot.plugins.worker.MarathonLatentWorker`. ``Marathon`` is a
  production-grade container orchestration platform for Mesosphere's Data-
  center Operating System (DC/OS) and Apache ``Mesos``.
- ``password`` in :py:class:`~buildbot.plugins.worker.DockerLatentWorker` and
  :py:class:`~buildbot.plugins.worker.HyperLatentWorker`, can be None. In that
  case, they will be auto-generated from random number.
- :bb:reporter:`StashStatusPush` now accepts ``key``, ``buildName``,
  ``endDescription``, ``startDescription``, and ``verbose`` parameters to
  control the JSON sent to Stash.
- Buildbot can now be configured to deny read access to REST api resources
  based on authorization rules.


Older Release Notes
~~~~~~~~~~~~~~~~~~~

.. toctree::
    :maxdepth: 1

    0.9.1
    0.9.0
    0.9.0rc4
    0.9.0rc3
    0.9.0rc2
    0.9.0rc1
    0.9.0b9
    0.9.0b8
    0.9.0b7
    0.9.0b6
    0.9.0b5
    0.9.0b4
    0.9.0b3
    0.9.0b2
    0.9.0b1
    0.8.12
    0.8.10
    0.8.9
    0.8.8
    0.8.7
    0.8.6

Note that Buildbot-0.8.11 was never released.
