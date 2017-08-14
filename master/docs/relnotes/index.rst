Release Notes
~~~~~~~~~~~~~
..
    Don't write to this file anymore!!

    Buildbot now uses towncrier to manage its release notes.
    towncrier helps to avoid the need for rebase when several people work at the same time on the releasenote files.

    Each PR should come with a file in the master/buildbot/newsfragment directory

.. towncrier release notes start

Buildbot ``0.9.10`` ( ``2017-08-03`` )
======================================

Bug fixes
---------

- Fix 'reconfig master causes worker lost' error (:issue:`3392`).
- Fix bug where object names could not be larger than 150 characters
  (:issue:`3449`)
- Fix bug where notifier names could not be overridden (:issue:`3450`)
- Fix exception when shutting down a master (:issue:`3478`)
- Fix Manhole support to work with Python 3 and Twisted 16.0.0+
  (:issue:`3160`). :py:class:`~buildbot.manhole.AuthorizedKeysManhole` and
  :py:class:`~buildbot.manhole.PasswordManhole` now require a directory
  containing SSH host keys to be specified.
- Fix python 3 issue with displaying the properties when fetching builders
  (:issue:`3418`).
- Fix bug when :py:class:`~buildbot.steps.shellsequence.ShellArg` arguments
  were rendered only once during an instance's lifetime.
- Fix waterfall tiny size of build status indicators (:issue:`3475`)
- Fix waterfall natural order of builder list
- Fix builder page use 'pointer' cursor style for tags (:issue:`3473`)
- Fix builder page update tag filter when using the browser's back button (:issue:`3474`)

Features
--------

- added support for builder names in REST API. Note that those endpoints are
  not (yet) available from the UI, as the events are not sent to the endpoints
  with builder names.
- Implemented new ability to set from by email domain. Implemented
  :py:class:`~buildbot.www.authz.RolesFromDomain`. (:issue:`3422`)


Buildbot ``0.9.9.post2`` ( ``2017-07-06`` )
===========================================

Bug fixes
---------

- Fix ``tried to complete 100 buildrequests, but only completed 25`` issue in
  buildrequest collapser (:issue:`3406`)

- Fixed issue when several mail notifiers are used with same parameters, but
  different modes (:issue:`3398`).

- Fixed release scripts for ``postN`` releases

Buildbot ``0.9.9.post1`` ( ``2017-07-01`` )
===========================================

Bug fixes
---------

- Fix regression with :py:class:`~buildbot.www.oauth2.GitHubAuth` when API v3 is used.
- When using the :py:class:`~buildbot.www.oauth2.GitHubAuth` v4 API,
  the generated GraphQL to get the user organizations uses a name alias for
  each organization. These aliases must not contain dashes.


Buildbot ``0.9.9`` ( ``2017-06-29`` )
=====================================

Bug fixes
---------

- Fixed a regression inn ``UserPasswordAuth`` where a list would create an
  error.
- Fix non ascii payload handling in base web hook (:issue:`3321`).
- Fixed default buildrequest collapsing (:issue:`3151`)
- _wait_for_request() would fail to format a log statement due to an invalid
  type being passed to log.msg (resulting in a broken build)
- Fix Windows compatibility with frontend development tool ``gulp dev proxy``
  (:issue:`3359`)

Features
--------

- New :ref:`Grid View <GridView>` UI plugin.
- The :ref:`Change-Hooks` system is now integrated in the :ref:`Plugins`
  system, making it easier to subclass hooks. There is still the need to re-
  factor hook by hook to allow better customizability.
- The :py:class:`~buildbot.www.oauth2.GitHubAuth` now allows fetching the user
  team membership for all organizations the user belongs to. This requires
  access to a V4 GitHub API(GraphQL).
- GitLab merge request hook now create a change with repository to be the
  source repository and branch the source branch. Additional properties are
  created to point to destination branch and destination repository. This makes
  :bb:reporter:`GitLabStatusPush` push the correct status to GitLab, so that
  pipeline report is visible in the merge request page.
- The :py:class:`~buildbot.www.hooks.github.GitHubEventHandler` now allows the
  inclusion of white-listed properties for push events.
- Allow sending a comment to a pull request for Bitbucket Server in
  :py:class:`~buildbot.reporters.stash.BitbucketServerPRCommentPush`
- Implement support for Bitbucket Server webhook plugin in
  :py:class:`~buildbot.www.hooks.bitbucketserver.BitbucketServerEventHandler`


Buildbot ``0.9.8`` ( ``2017-06-14`` )
=====================================

Core Bug fixes
--------------

- Fix incompatibility issue of ``UserPasswordAuth`` with python 3.
- Fix issue with oauth sequence not working with Firefox (:issue:`3306`)
- Update old ``addChange`` method to accept the new chdict names if only the
  new name is present. Fixes :issue:`3191`.
- fix bytes vs string issue on python3 with authorization of rest endpoints.

Core Features
-------------

- ``doStepIf`` is now renderable.
- Source step codebase is now renderable.
- Step names are now renderable.
- Added :py:func:`giturlparse` utility function to help buildbot components
  like reporters to parse git url from change sources.
- Factorized the mail reporter to be able to write new message based reporters, for other backend than SMTP.
- The class :py:class:`~buildbot.process.properties.Property` now allows being
  used with Python built in comparators. It will return a Renderable which
  executes the comparison.

Components Bug fixes
--------------------

- GitLab reporter now correctly sets the status to running instead of pending
  when a build starts.
- GitLab reporter now correctly works when there are multiple codebase, and
  when the projects names contain url reserved characters.
- GitLab reporter now correctly reports the status even if there are several
  sourcestamps. Better parsing of change repository in GitLab reporter so that
  it understands ssh urls and https url. GitLab reporter do not use the project
  field anymore to know the repository to push to.

Components Features
-------------------

- GitLab hook now supports the merge_request event to automatically build from
  a merge request. Note that the results will not properly displayed in
  merge_request UI due to https://gitlab.com/gitlab-org/gitlab-ce/issues/33293
- Added a https://pushjet.io/ reporter as
  :py:class:`buildbot.reporters.pushjet.PushjetNotifier`
- New build step :py:class:`~buildbot.steps.master.Assert` Tests a renderable
  or constant if it evaluates to true. It will succeed or fail to step
  according to the result.

Buildbot ``0.9.7`` ( ``2017-05-09`` )
=====================================================

Core Bug fixes
--------------

- Fix :py:class:`UserPasswordAuth` authentication on ``py3`` and recent
  browsers. (:issue:`3162`, :issue:`3163`). The ``py3`` fix also requires
  Twisted https://github.com/twisted/twisted/pull/773.
- :ref:`ConsoleView` now display changes the same way as in Recent Changes
  page.
- Fix issue with :ref:`ConsoleView` when no change source is configured but
  still builds have ``got_revision`` property

Components Bug fixes
--------------------

- Allow renderables in options and definitions of step ``CMake``. Currently
  only dicts and lists with renderables inside are allowed.
- ``OAuth`` Authentication are now working with :py:class:`RolesFromEmails`.
- :py:class:`~buildbot.worker.docker.DockerLatentWorker`: ``_image_exists``
  does not raise anymore if it encounters an image with ``<none>`` tag
- Fix command line parameters for ``Robocopy`` step ``verbose`` option

Core Features
-------------

- Builds ``state_string`` is now automatically computed according to the
  :py:meth:`BuildStep.getResultSummary`, :py:attr:`BuildStep.description` and
  ``updateBuildSummaryPolicy`` from :ref:`Buildstep-Common-Parameters`. This
  allows the dashboards and reporters to get a descent summary text of the
  build without fetching the steps.
- New :bb:cfg:`configurators` section, which can be used to create higher level
  configuration modules for Buildbot.
- New :bb:configurator:`JanitorConfigurator` which can be used to create a
  builder which save disk space by removing old logs from the database.

Components Features
-------------------

- Added a https://pushover.net/ reporter as :py:class:`buildbot.reporters.pushover.PushoverNotifier`
- ``property`` argument in SetPropery is now renderable.


Buildbot ``0.9.6`` ( ``2017-04-19`` )
=====================================================

Core Bug fixes
--------------

- :py:class:`buildbot.www.authz.endpointmatchers.AnyControlEndpointMatcher` now
  actually doesn't match `GET` requests. Before it would act like an
  `AnyEndpointMatcher` since the `GET` had a different case.
- Passing ``unicode`` ``builderNames`` to :bb:sched:`ForceScheduler` no longer
  causes an error.
- Fix issue with :bb:sched::`Nightly` change classification raising foreign key
  exceptions (:issue:`3021`)
- Fixes an exception found :py:func:`buildbot_net_usage_data._sendWithUrlib` when running through the tutorial using Python 3.
- ``usePTY`` configuration of the :bb:step:`ShellCommand` now works as expected
  with recent version of buildbot-worker.

Components Bug fixes
--------------------
- ``pollAtLaunch`` of the :bb:chsrc:`GitHubPullrequestPoller` now works as
  expected. Also the author email won't be displayed as None
- :bb:chsrc:`GerritChangeSource` and :bb:reporter:`GerritStatusPush` now use the master's environment including PATH variable to find
  the ssh binary.
- :py:class:`~buildbot_worker.commands.transfer.SlaveDirectoryUploadCommand`
  no longer throws exceptions because the file "is used by another process"
  under Windows

UI Bug fixes
------------

- Fix waterfall scrolling and zooming in current browsers
- ``console_view`` now properly uses ``revlink`` metadata to link to changes.
- Fixed Console View infinite loading spinner when no change have been recorded
  yet (:issue:`3060`).

Core Features
-------------

- new :ref:`Virtual-Builders` concept for better integration of frameworks
  which store the build config along side the source code.

Components Features
-------------------

- :bb:chsrc:`BitBucket` now sets the ``event``
  property on each change to what the ``X-Event-Key`` header contains.
- :bb:chsrc:`GitHubPullrequestPoller` now adds additional information about the
  pull request to properties. The property argument is removed and is populated
  with the repository full name.
- :bb:chsrc:`GitHub` now sets
  the ``event`` property on each change to what the ``X-GitHub-Event`` header
  contains.
- Changed :py:class:`~buildbot.www.oauth2.GitHubAuth` now supports GitHub
  Enterprise when setting new ``serverURL`` argument.
- :bb:chsrc:`GitLab` now sets the ``event`` property
  on each change to what the ``X-GitLab-Event`` header contains.
- :bb:chsrc:`GitHub` now process
  git tag push events
- :bb:chsrc:`GitHub` now adds
  more information about the pull request to the properties. This syncs
  features with :bb:chsrc:`GitHubPullrequestPoller`
- :bb:chsrc:`GitLab` now process git tag push
  events
- :bb:chsrc:`GitLab` now supports authentication
  with the secret token

UI Features
-----------
- Reworked :ref:`ConsoleView` and :ref:`WaterfallView` for better usability and better integration with virtual builders
- :ref:`WWW-data-module` collections now have a ``$resolved`` attribute which
  allows dashboard to know when the data is loaded.


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
  :py:class:`~buildbot.reporters.GitLabStatusPush`
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
- :bb:reporter:`BitbucketServerStatusPush` now accepts ``key``, ``buildName``,
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
