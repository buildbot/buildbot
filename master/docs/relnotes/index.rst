Release Notes
~~~~~~~~~~~~~
..
    Don't write to this file anymore!!

    Buildbot now uses towncrier to manage its release notes.
    towncrier helps to avoid the need for rebase when several people work at the same time on the releasenote files.

    Each PR should come with a file in the master/buildbot/newsfragment directory

.. towncrier release notes start

Buildbot ``0.9.5`` ( ``2017-03-18`` )
===================================================

Bug fixes
---------

- Fix issue with compressing empty log
- Fix issue with db being closed by wrong thread
- Fix issue with buildbot_worker not closing file handles when using the
  transfer steps
- Fix issue with buildbot requesting too many permissions from GitHub's OAuth
- Fix :py:class:`~buildbot.steps.http.HTTPStep` to accept ``json`` as keyword
  argument.
- Updated :py:class:`~buildbot.workers.openstack.OpenStackLatentWorker` to use
  keystoneauth1 so it will support latest python-novaclient packages.
- Include :py:class:`~buildbot.steps.package.rpm.rpmlint.RpmLint` step in steps
  plugins.

Core Features
-------------

- Experimental support for Python 3.5 and 3.6.
  Note that complete support depends on fixes to be released in Twisted 17.2.0.
- New experimental :ref:`secretManagement` framework, which allows to securely declare secrets, reusable in your steps.
- New :ref:`buildbot_wsgi_dashboards` plugin, which allows to write custom
  dashboard with traditional server side web frameworks.
- Added :py:class:`AnyControlEndpointMatcher` and
  :py:class:`EnableSchedulerEndpointMatcher` for better configurability of the
  access control. If you have access control to your Buildbot, it is
  recommended you add :py:class:`AnyControlEndpointMatcher` at the end of your
  access control configuration.

- Schedulers can now be toggled on and off from the UI. Useful for temporarily
  disabling periodic timers.

Components Features
-------------------

- :py:class:`~buildbot.steps.transfer.FileUpload` now supports setting the url
  title text that is visible in the web UI. :py:class:`~buildbot.steps.transfer.FileUpload` now supports custom `description` and
  `descriptionDone` text.
- :py:class:`~buildbot.worker.ec2.EC2LatentWorker` now provides instance id as
  the `instance` property enabling use of the AWS toolkit.
- Add GitHub pull request Poller to list of available changesources.
- :py:class:`~buildbot.util.OAuth2LoginResource` now supports the `token` URL
  parameter. If a user wants to authenticate through OAuth2 with a pre-
  generated token (such as the `access_token` provided by GitHub) it can be
  passed to `/auth/login` as the `token` URL parameter and the user will be
  authenticated to buildbot with those credentials.
- New reporter :py:class:`~buildbot.reporters.github.GitHubCommentPush` can
  comment on GitHub PRs
- :py:class:`~buildbot.changes.GitPoller` now supports polling tags in a git
  repository.
- :py:class:`~buildbot.steps.transfer.MultipleFilUpload` now supports the
  `glob` parameter. If `glob` is set to `True` all `workersrcs` parameters will
  be run through `glob` and the result will be uploaded to `masterdest`
- Changed :py:class:`~buildbot.workers.openstack.OpenStackLatentWorker` to
  default to v2 of the Nova API. The novaclient package has had a deprecation
  warning about v1.1 and would use v2 anyway.

Deprecations and Removals
-------------------------

- ``master/contrib`` and ``worker/contrib`` directories have been moved to
  their own repository at https://github.com/buildbot/buildbot-contrib/


Buildbot ``0.9.4`` ( ``2017-02-08`` )
=====================================

Database upgrade
----------------

A database upgrade is necessary for this release (see :bb:cmdline:`upgrade-master`).

Bug fixes
---------

- Like for ``buildbot start``, ``buildbot upgrade-master`` will now erase an old pidfile if the process is not live anymore instead of just failing.
- Change properties 'value' changed from String(1024) to Text. Requires upgrade master. (:bug:`3197`)
- When using REST API, it is now possible to filter and sort in descending order at the same time.
- Fix issue with :bb:reporter:`HttpStatusPush` raising ``datetime is not JSON serializable`` error.
- Fix issue with log viewer not properly rendering color codes.
- Fixed log viewer selection and copy-paste for Firefox (:bug:`3662`).
- Fix issue with ``DelayedCalled`` already called, and worker missing notification email never received.
- :bb:cfg:`schedulers` and :bb:cfg:`change_source` are now properly taking configuration change in account with ``buildbot reconfig``.
- ``setuptools`` is now explicitly marked as required. The dependency was previously implicit.
- :bb:cfg:`buildbotNetUsageData` now uses ``requests`` if available and will default to HTTP if a bogus SSL implementation is found.
  It will also correctly send information about the platform type.

Features
--------

- Buildbot now uses `JWT <https://en.wikipedia.org/wiki/JSON_Web_Token>`_ to
  store its web UI Sessions.
  Sessions now persist upon buildbot restart.
  Sessions are shared between masters.
  Session expiration time is configurable with ``c['www']['cookie_expiration_time']`` see :bb:cfg:`www`.
- Builders page has been optimized and can now be displayed with 4 http requests whatever is the builder count (previously, there was one http request per builder).
- Builder and Worker page build list now have the ``numbuilds=`` option which allows to show more builds.
- Masters page now shows more information about a master (workers, builds, activity timer)
- Workers page improvements:

    - Shows which master the worker is connected to.
    - Shows correctly the list of builders that this master is configured on (not the list of ``buildermaster`` which nobody cares about).
    - Shows list of builds per worker similar to the builders page.
    - New worker details page displays the list of builds built by this worker using database optimized query.

Deprecations and Removals
-------------------------

- Some deprecated broken :ref:`Contrib-Scripts` were removed.
- :py:data:`buildbot.www.hooks.googlecode` has been removed, since the Google Code service has been shut down.
- :py:data:`buildbot.util.json` has been deprecated in favor of the standard library :py:mod:`json`.
  ``simplejson`` will not be used anymore if found in the virtualenv.


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
