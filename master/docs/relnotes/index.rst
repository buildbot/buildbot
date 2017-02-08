Release Notes
~~~~~~~~~~~~~
..
    Don't write to this file anymore!!

    Buildbot now uses towncrier to manage its release notes.
    towncrier helps to avoid the need for rebase when several people work at the same time on the releasenote files.

    Each PR should come with a file in the master/buildbot/newsfragment directory

.. towncrier release notes start

Buildbot ``0.9.4`` ( ``2017-02-08`` )
===================================================

Bug fixes
---------

- Fix issue with log viewer not properly rendering color codes.
- Like for ``buildbot start``, ``buildbot upgrade-master`` will now erase an
  old pidfile if the process is not live anymore instead of just failing.
- Change properties 'value' changed from String(1024) to Text. Requires upgrade
  master. (:bug:`3197`)
- When using REST API it is now possible to filter and sort in descending order
  at the same time.
- Fix issue with :bb:reporter:`HttpStatusPush` raising datetime is not JSON
  serializable error.
- Fixed log viewer selection and copy-paste for Firefox (:bug:`3662`).
- Fix issue with ``DelayedCalled`` already called, and worker missing
  notification email never received.
- :bb:cfg:`schedulers`. and :bb:cfg:`change_source` are now properly taking
  configuration change in account with ``buildbot reconfig``.
- ``setuptools`` is now explicitly marked as required. The dependency was
  previously implicit.
- :bb:cfg:`buildbotNetUsageData` now uses ``requests`` if available and will
  default to HTTP if a bogus SSL implementation is found. It will also
  correctly send information about the platform type.

Features
--------

- Builders page has been optimized and can now be displayed with 4 http
  requests whatever is the builder count.
- Buildbot now uses `JWT <https://en.wikipedia.org/wiki/JSON_Web_Token>`_ to
  store its web UI Sessions. Sessions now persist upon buildbot restart.
  Sessions are shared between masters. Session expiration time is configurable
  with ``c['www']['cookie_expiration_time']`` see :bb:cfg:`www`.
- Masters page now shows more information about a master (workers, builds,
  activity timer)
- Builder and Worker page build list now have the ``numbuilds=`` option which
  allows to show more builds.
- Workers page improvement: Shows which master the worker is connected to.
  Shows correctly the list of builders that this master is configured on (not
  the list of ``buildermaster`` which nobody cares about). Shows list of builds
  per worker similar to the builders page. New worker details page displays the
  list of builds built by this worker using database optimized query.

Misc
----

- absolute_import+print_function



Deprecations and Removals
-------------------------

- Some deprecated :ref:`Contrib-Scripts` were removed.
- :py:data:`buildbot.www.hooks.googlecode` has been removed, since the Google
  Code service has been shut down.
- :py:data:`buildbot.util.json` has been deprecated in favor of the standard
  library :py:mod:`json`.


Buildbot ``0.9.3`` ( ``2017-01-11`` )
===================================================

Bug fixes
---------

- Fix :bb:reporter:`BitbucketStatusPush` ``ep should start with /`` assertion
  error.
- Fix duplicate worker use case, where a worker with the same name would make
  the other worker also disconnect (:bug:`3656`)
- :py:class:`~buildbot.changes.GitPoller`: ``buildPushesWithNoCommits`` now
  rebuilds for a known branch that was updated to an existing commit.
- Fix issue with log viewer not staying at bottom of the log when loading log
  lines.
- Fixed `addBuildURLs` in :py:class:`~buildbot.steps.trigger.Trigger` to use
  results from triggered builds to include in the URL name exposed by API.
- Fix :ref:`mq-Wamp` :bb:cfg:`mq` support by removing ``debug``, ``debug_amp``
  and ``debug_app`` from the :bb:cfg:`mq` config, which is not available in
  latest version of `Python Autobahn <http://autobahn.ws>`_. You can now use
  ``wamp_debug_level`` option instead.
- fix issue with factory.workdir AttributeError are not properly reported.

Features
--------

- Optimize the memory consumption of the log compression process. Buildbot do
  not load the whole log into memory anymore. This should improve a lot
  buildbot memory footprint.
- Changed the build page so that the preview of the logs are shown in live. It
  is a preview means the last lines of log. How many lines is configurable per
  user in the user settings page.
- Log viewer line numbers are no longer selectable, so that it is easier to
  copy paste.
- :py:class:`~buildbot.plugins.worker.DockerLatentWorker` accepts now
  renderable Dockerfile
- :ref:`Renderer` function can now return
  :class:`~buildbot.interfaces.IRenderable` objects.
- new :bb:step:`SetProperties` which allows to generate and transform
  properties separately.
- Handle new workers in `windows_service.py` script.
- Sort the builders in the waterfall view by name instead of ID.


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
