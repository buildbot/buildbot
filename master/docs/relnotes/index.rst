Release Notes
~~~~~~~~~~~~~
..
    Don't write to this file anymore!!

    Buildbot now uses towncrier to manage its release notes.
    towncrier helps to avoid the need for rebase when several people work at the same time on the releasenote files.

    Each PR should come with a file in the master/buildbot/newsfragment directory

.. towncrier release notes start

Buildbot ``2.8.4`` ( ``2020-08-29`` )
=====================================

Bug fixes
---------

- Fix 100% CPU on large installations when using the changes API (:issue:`5504`)
- Work around incomplete support for codebases in ``GerritChangeSource`` (:issue:`5190`). This avoids an internal assertion when the configuration file does not specify any codebases.
- Add missing VS2017 entry points.


Buildbot ``2.8.3`` ( ``2020-08-22`` )
=====================================

Bug fixes
---------

- Fix Docker image building for the master which failed due to mismatching versions of Alpine (:issue:`5469`).


Buildbot ``2.8.2`` ( ``2020-06-14`` )
=====================================

Bug fixes
---------

- Fix crash in Buildbot Windows service startup code (:issue:`5344`)


Buildbot ``2.8.1`` ( ``2020-06-06`` )
=====================================

Bug fixes
---------

- Fix source distribution missing required buildbot.test.fakedb module for unit tests.
- Fix crash in trigger step when renderables are used for scheduler names (:issue:`5312`)


Buildbot ``2.8.0`` ( ``2020-05-27`` )
=====================================

Bug fixes
---------

- Fix :py:class:`GitHubEventHandler` to include files in `Change` that comes from a github PR (:issue:`5294`)
- Updated the `Docker` container `buildbot-master` to `Alpine 3.11` to fix
  segmentation faults caused by an old version of `musl`
- Base64 encoding logs and attachments sent via email so emails conform to RFC 5322 2.1.1
- Handling the case where the BitbucketStatusPush return code is not 200
- When cancelling a buildrequest, the reason field is now correctly transmitted all the way to the cancelled step.
- Fix Cache-control header to be compliant with RFC 7234 (:issue:`5220`)
- Fix :py:class:`GerritEventLogPoller` class to be declared as entry_point (can be used in master.cfg file)
- Git poller: add `--ignore-missing` argument to `git log` call to avoid `fatal: bad object` errors
- Log watcher looks for the "tail" utility in the right location on Haiku OS.
- Add limit and filtering support for the changes data API as described in :issue:`5207`

Improved Documentation
----------------------

- Make docs build with the latest sphinx and improve rendering of the example HTML file for custom dashboard
- Make docs build with Sphinx 3 and fix some typos and incorrect Python module declarations

Features
--------

- :class:`Property` and :class:`Interpolate` objects can now be compared. This will generate a renderable that will be evaluated at runtime. see :ref:`RenderableComparison`.
- Added argument `count` to lock access to allow a lock to consume a variable amount of units
- Added arguments `pollRandomDelayMin` and `pollRandomDelayMax` to `HgPoller`, `GitPoller`, `P4Poller`, `SvnPoller` to spread the polling load

Deprecations and Removals
-------------------------

- Removed `_skipChecks` from `LockAccess` as it's obsolete


Buildbot ``2.7.0`` ( ``2020-02-27`` )
=====================================

Bug fixes
---------

- Command `buildbot-worker create-worker` now supports ipv6 address for buildmaster connection.
- Fix crash in latent worker stopService() when the worker is insubstantiating (:issue:`4935`).
- Fix race condition between latent worker's stopService() and substantiate().
- :class:`GitHubAuth` is now using `Authorization` headers instead of `access_token` query parameter, as the latter was deprecated by Github. (:issue:`5188`)
- ``jQuery`` and ``$`` are available again as a global variable for UI plugins (:issue:`5161`).
- Latent workers will no longer wait for builds to finish when worker is reconfigured.
  The builds will still be retried on other workers and the operators will not need to potentially wait multiple hours for builds to finish.
- p4poller will no longer override Perforce login ticket handling behavior which fixes random crashes (:issue:`5042`).

Improved Documentation
----------------------

- The procedures of upgrading to Buildbot 1.x and 2.x have been clarified in separate documents.
- The layout of the specification of the REST API has been improved.
- Updated newsfragments README.txt to no longer refer to renamed class :py:class:`~buildbot.reporters.http.HttpStatusBase`
- The documentation now uses the read-the-docs theme which is more readable.

Features
--------

- A new www badges style was added: ``badgeio``
- :py:class:`~buildbot.reporters.http.HttpStatusPushBase` now allows you to skip unicode to bytes encoding while pushing data to server
- New ``buildbot-worker create-worker --delete-leftover-dirs`` option to automatically remove obsolete builder directories


Buildbot ``2.6.0`` ( ``2020-01-21`` )
=====================================

Bug fixes
---------

- Fix a potential deadlock when interrupting a step that is waiting for a lock to become available.
- Prepare unique hgpoller name when using multiple hgpoller for multiple branches (:issue:`5004`)
- Fix hgpoller crash when force pushing a branch (:issue:`4876`)
- Fix mail recipient formatting to make sure address comments are separately escaped instead of escaping the whole To: or CC: header, which is not RFC compliant.
- Master side keep-alive requests are now repeated instead of being single-shot (:issue:`3630`).
- The message queues will now wait until the delivered callbacks are fully completed during shutdown.
- Fix encoding errors during P4Poller ticket parsing :issue:`5148`.
- Remove server header from HTTP response served by the web component.
- Fix multiple race conditions in Telegram reporter that were visible in tests.
- The Telegram reporter will now wait until in-progress polls finish during shutdown.
- Improve reliability of timed scheduler.
- transfer steps now correctly report errors from workers :issue:`5058`
- Warn if Buildbot title in the configuration is too long and will be ignored.
- Worker will now wait for any pending keep-alive requests to finish leaving them in indeterminate state during shutdown.

Improved Documentation
----------------------

- Mention that QueueRef.stopConsuming() may return a Deferred.

Features
--------

- Add the parameter --use-tls to `buildbot-worker create-worker` to automatically enable TLS in the connection string
- Gerrit reporter now passes a tag for versions that support it.
  This enables filtering out buildbot's messages.
- :py:class:`GerritEventLogPoller` and :py:class:`GerritChangeSource` coordinate so as not to generate duplicate changes, resolves :issue:`4786`
- Web front end now allows you to configure the default landing page with `c['www']['default_page'] = 'name-of-page'`.
- The new option dumpMailsToLog of MailNotifier allows to dump formatted mails to the log before sending.
- bb:cfg:`workers` will now attempt to read ``/etc/os-release`` and stores them into worker info as ``os_<field>`` items.
  Add new interpolation ``worker`` that can be used for accessing worker info items.


Buildbot ``2.5.1`` ( ``2019-11-24`` )
=====================================

Bug fixes
---------

- Updates supported browser list so that Ubuntu Chromium will not always be flagged as out of date.
- Fixed IRC notification color of cancelled builds.
- Updated url in description of worker service for Windows (no functionality impact).
- Updated templates of www-badges to support additional padding configuration (:issue:`5079`)
- Fix issue with custom_templates loading path (:issue:`5035`)
- Fix url display when step do not contain any logs (:issue:`5047`)


Buildbot ``2.5.0`` ( ``2019-10-17`` )
=====================================

Bug fixes
---------

- Fix crash when reconfiguring changed workers that have new builders assigned to them (:issue:`4757`, :issue:`5027`).
- DockerLatentWorker: Allow to bind the same volume twice into a worker's container, Buildbot now requires 'docker-py' (nowadays 'docker') version 1.2.3+ from 2015.
- IRC bot can have authz configured to create or stop builds (:issue:`2957`).
- Fix javascript exception with grid view tag filtering (:issue:`4801`)

Improved Documentation
----------------------

- Changed PluginList link from trac wiki directly to the GitHub wiki.

Features
--------

- Created a `TelegramBot` for notification and control through Telegram messaging app.
- Added support for environment variable P4CONFIG to class ``P4Source``
- Allow to define behavior for GitCommit when there is nothing to commit.
- Add support for revision links to Mercurial poller
- Support recursive matching ('**') in MultipleFileUpload when `glob=True` (requires python3.5+ on the worker)


Buildbot ``2.4.1`` ( ``2019-09-11`` )
=====================================

Bug fixes
---------

- allow committer of a change to be null for new setups (:issue:`4987`)
- custom_templates are now working again.
- Locks will no longer allow being acquired more times than the `maxCount` parameter if this parameter is changed during master reconfiguration.

Features
--------

- Improve log cleaning performance by using delete with join on supported databases.
- Hiding/showing of inactive builders is now possible in Waterfall view.


Buildbot ``2.4.0`` ( ``2019-08-18`` )
=====================================

Highlights
----------

Database upgrade may take a while on larger instances on this release due to newly added index.

Bug fixes
---------

- Add an index to ``steps.started_at`` to boost expensive SQL queries.
- Fix handling of the ``refs_changed`` event in the BitBucket Server web hook.
- Fix errors when disconnecting a libvirt worker (:issue:`4844`).
- Fix Bitbucket Cloud hook crash due to changes in their API (:issue:`4873`).
- Fix ``GerritEventLogPoller`` was using the wrong date format.
- Fix janitor Exception when there is no logchunk to delete.
- Reduced the number of SQL queries triggered by ``getPrevSuccessfulBuild()`` by up to 100.
- :py:class:`~buildbot.util.git.GitStepMixin`: Prevent builders from corrupting temporary ssh data path by using builder name as part of the path
- :py:class:`~buildbot.util.git.GitTag`: Allow ``tagName`` to be a renderable.
- Fix Github error reporting to handle exceptions that happen before the HTTP request is sent.
- :py:class:`~buildbot.changes.gitpoller.GitPoller`: Trigger on pushes with no commits when the new revision is not the tip of another branch.
- :py:class:`~buildbot.steps.source.git.Git`: Fix the invocation of ``git submodule foreach`` on cleaning.
- Fix StatsService not correctly clearing old consumers on reconfig.
- Fix various errors in try client with Python 3 (:issue:`4765`).
- Prevent accidental start of multiple force builds in web UI (:issue:`4823`).
- The support for proxying Buildbot frontend to another Buildbot instance during development has been fixed.
  This feature has been broken since v2.3.0, and is now completely re-implemented for best performance, ease of use and maintainability.

Improved Documentation
----------------------

- Document why some listed icons may not work out-of-the-box when building a custom dashboard (:issue:`4939`).
- Improve Vault secrets management documentation and examples.
- Link the documentation of ``www.port`` to the capabilities of ``twisted.application.strports``.
- Move the documentation on how to submit PRs out of the trac wiki to the documentation shipped with Buildbot, update and enhance it.

Features
--------

- Update buildbot worker image to Ubuntu 18.04 (:issue:`4928`).
- :py:class:`~buildbot.worker.docker.DockerLatentWorker`: Added support for docker build contexts, ``buildargs``, and specifying controlling context.
- The :py:class:`~buildbot.changes.gerritchangesource.GerritChangeFilter` and :py:class:`~buildbot.changes.gerritchangesource.GerritEventLogPoller` now populate the ``files`` attribute of emitted changes when the ``get_files`` argument is true. Enabling this feature triggers an additional HTTP request or SSH command to the Gerrit server for every emitted change.
- Buildbot now warns users who connect using unsupported browsers.
- Boost janitor speed by using more efficient SQL queries.
- Scheduler properties are now renderable.
- :py:class:`~buildbot.steps.python.Sphinx`: Added ``strict_warnings`` option to fail on warnings.
- UI now shows a paginated view for trigger step sub builds.

Deprecations and Removals
-------------------------

- Support for older browsers that were not working since 2.3.0 has been removed due to technical limitations.
  Notably, Internet Explorer 11 is no longer supported.
  Currently supported browsers are Chrome 56, Firefox 52, Edge 13 and Safari 10, newer versions of these browsers and their compatible derivatives.
  This set of browsers covers 98% of users of buildbot.net.


Buildbot ``2.3.1`` ( ``2019-05-22`` )
=====================================

Bug fixes
---------

- Fix vulnerability in OAuth where user-submitted authorization token was used for authentication
  (https://github.com/buildbot/buildbot/wiki/OAuth-vulnerability-in-using-submitted-authorization-token-for-authentication)
  Thanks to Phillip Kuhrt for reporting it.

Buildbot ``2.3.0`` ( ``2019-05-06`` )
=====================================

Highlights
----------

- Support for older browsers has been hopefully temporarily broken due to frontend changes in progress.
  Notably, Internet Explorer 11 is not supported in this release.
  Currently supported browsers are Chrome 56, Firefox 52, Edge 13 and Safari 10, newer versions of these browsers and their compatible derivatives.
  This set of browsers covers 98% of users of buildbot.net.

Bug fixes
---------

- Fixed :bb:step:`Git` to clean the repository after the checkout when submodules are enabled. Previously this action could lead to untracked module directories after changing branches.
- Latent workers with negative `build_wait_timeout` will be shutdown on master shutdown.
- Latent worker will now wait until `start_instance()` before starting `stop_instance()` or vice-versa. Master will wait for these functions to finish during shutdown.
- Latent worker will now correctly handle synchronous exception from the backend worker driver.
- Fixed a potential error during database migration when upgrading to versions >=2.0 (:issue:`4711`).

Deprecations and Removals
-------------------------

- The implementation language of the Buildbot web frontend has been changed from CoffeeScript to JavaScript.
  The documentation has not been updated yet, as we plan to transition to TypeScript.
  In the transitory period support for some browsers, notably IE 11 has been dropped.
  We hope to bring support for older browsers back once the transitory period is over.
- The support for building Buildbot using npm as package manager has been removed.
  Please use yarn as a replacement that is used by Buildbot developers.

Buildbot ``2.2.0`` ( ``2019-04-07`` )
=====================================

Bug fixes
---------

- Fix passing the verify and debug parameters for the HttpStatusPush reporter
- The builder page UI now correctly shows the list of owners for each build.
- Fixed bug with tilde in git repo url on Python 3.7 (:issue:`4639`).
- Fix secret leak when non-interpolated secret was passed to a step (:issue:`4007`)

Features
--------

- Added new :bb:step:`GitCommit` step to perform git commit operation
- Added new :bb:step:`GitTag` step to perform git tag operation
- HgPoller now supports bookmarks in addition to branches.
- Buildbot can now monitor multiple branches in a Mercurial repository.
- :py:class:`~buildbot.www.oauth2.OAuth2Auth` have been adapted to support ref:`Secret`.
- Buildbot can now get secrets from the unix password store by `zx2c4` (https://www.passwordstore.org/).
- Added a ``basename`` property to the Github pull request webhook handler.
- The GitHub change hook secret can now be rendered.
- Each build now gets a preparation step which counts the time spend starting latent worker.
- Support known_hosts file format as ``sshKnownHosts`` parameter in SSH-related operations (:issue:`4681`)


Buildbot ``2.1.0`` ( ``2019-03-09`` )
=====================================

Highlights
----------

- Worker to Master protocol can now be encrypted via TLS.

Bug fixes
---------

- To avoid database corruption, the ``upgrade-master`` command now ignores all
  signals except ``SIGKILL``. It cannot be interrupted with ``ctrl-c``
  (:issue:`4600`).
- Fixed incorrect tracking of latent worker states that could sometimes result
  in duplicate ``stop_instance`` calls and so on.
- Fixed a race condition that could manifest in cancelled substantiations if
  builds were created during insubstantiation of a latent worker.
- Perforce CLI Rev. 2018.2/1751184 (2019/01/21) is now supported
  (:issue:`4574`).
- Fix encoding issues with Forcescheduler parameters error management code.

Improved Documentation
----------------------

- fix grammar mistakes and use Uppercase B for Buildbot

Features
--------

- :py:class:`~buildbot-worker.buildbot_worker.bot.Worker` now have
  `connection_string` kw-argument which can be used to connect to a master
  over TLS.
- Adding 'expand_logs' option for LogPreview related settings.
- Force schedulers buttons are now sorted by their name. (:issue:`4619`)
- :bb:cfg:`workers` now have a new ``defaultProperties`` parameter.


Buildbot ``2.0.1`` ( ``2019-02-06`` )
=====================================

Bug fixes
---------

- Do not build universal python wheels now that Python 2 is not supported.
- Print a warning discouraging users from stopping the database migration.


Buildbot ``2.0.0`` ( ``2019-02-02`` )
=====================================

Deprecations and Removals
-------------------------

- Removed support for Python <3.5 in the buildbot master code.
  Buildbot worker remains compatible with python2.7, and interoperability tests are run continuously.
- APIs that are not documented in the official Buildbot documentation have been
  made private. Users of these undocumented APIs are encouraged to file bugs to
  get them exposed.
- Removed support of old slave APIs from pre-0.9 days. Using old APIs may fail
  silently. To avoid weird errors when upgrading a Buildbot installation that
  may use old APIs, first upgrade to to 1.8.0 and make sure there are no
  deprecated API warnings.
- Remove deprecated default value handling of the ``keypair_name`` and
  ``security_name`` attributes of ``EC2LatentWorker``.
- Support for ``Hyper.sh`` containers cloud provider has been removed as this
  service has shutdown.

Bug fixes
---------

- Fix CRLF injection vulnerability with validating user provided redirect parameters (https://github.com/buildbot/buildbot/wiki/CRLF-injection-in-Buildbot-login-and-logout-redirect-code)
  Thanks to ``mik317`` and ``mariadb`` for reporting it.

- Fix lockup during master shutdown when there's a build with unanswered ping
  from the worker and the TCP connection to worker is severed (issue:`4575`).
- Fix RemoteUserAuth.maybeAutLogin consumes bytes object as str leading to
  TypeError during JSON serialization. (:issue:`4402`)
- Various database integrity problems were fixed. Most notably, it is now
  possible to delete old changes without wiping all "child" changes in cascade
  (:issue:`4539`, :pull:`4536`).
- The GitLab change hook secret is now rendered correctly. (:issue:`4118`).

Features
--------

- Identifiers can now contain UTF-8 characters which are not ASCII. This
  includes worker names, builder names, and step names.

Older Release Notes
~~~~~~~~~~~~~~~~~~~

.. toctree::
    :maxdepth: 1

    1.x
    0.9.2-0.9.15
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
