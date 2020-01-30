Release Notes
~~~~~~~~~~~~~
..
    Don't write to this file anymore!!

    Buildbot now uses towncrier to manage its release notes.
    towncrier helps to avoid the need for rebase when several people work at the same time on the releasenote files.

    Each PR should come with a file in the master/buildbot/newsfragment directory

.. towncrier release notes start

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

Buildbot ``1.8.2`` ( ``2019-05-22`` )
=====================================

Bug fixes
---------

- Fix vulnerability in OAuth where user-submitted authorization token was used for authentication
  (https://github.com/buildbot/buildbot/wiki/OAuth-vulnerability-in-using-submitted-authorization-token-for-authentication)
  Thanks to Phillip Kuhrt for reporting it.

Buildbot ``1.8.1`` ( ``2019-02-02`` )
=====================================

Bug fixes
---------

- Fix CRLF injection vulnerability with validating user provided redirect parameters (https://github.com/buildbot/buildbot/wiki/CRLF-injection-in-Buildbot-login-and-logout-redirect-code)
  Thanks to ``mik317`` and ``mariadb`` for reporting it.

Buildbot ``1.8.0`` ( ``2019-01-20`` )
=====================================

Bug fixes
---------

- Fix a regression present in v1.7.0 which caused buildrequests waiting for a
  lock that got released by an unrelated build not be scheduled (:issue:`4491`)
- Don't run builds that request an instance with incompatible properties on
  Docker, Marathon and OpenStack latent workers.
- Gitpoller now fetches only branches that are known to exist on remote.
  Non-existing branches are quietly ignored.
- The demo repo in sample configuration files and the tutorial is now fetched
  via ``https:`` instead of ``git:`` to make life easier for those behind
  firewalls and/or using proxies.
- `buildbot sendchange` has been fixed on Python 3 (:issue:`4138`)

Features
--------

- Add a :py:class:`~buildbot.worker.kubernetes.KubeLatentWorker` to launch
  workers into a kubernetes cluster
- Simplify/automate configuration of worker as Windows service - eliminate
  manual configuration of Log on as a service

Deprecations and Removals
-------------------------

- The deprecated ``BuildMaster.addBuildset`` method has been removed. Use
  ``BuildMaster.data.updates.addBuildset`` instead.
- The deprecated ``BuildMaster.addChange`` method has been removed. Use
  ``BuildMaster.data.updates.addChange`` instead.
- ``buildbot`` package now requires Twisted versions >= 17.9.0. This is
  required for Python 3 support. Earlier versions of Twisted are not supported.


Buildbot ``1.7.0`` ( ``2018-12-21`` )
=====================================

Bug fixes
---------

- Fixed JSON decoding error when sending build properties to www change hooks
  on Python 3.
- Buildbot no longer attempts to start builds that it can prove will have
  unsatisfied locks.
- Don't run builds that request images or sizes on instances started with
  different images or sizes.

Features
--------

- The Buildbot master Docker image at https://hub.docker.com/r/buildbot/ has
  been upgraded to use Python 3.7 by default.
- Builder page has been improved with a smoothed build times plot, and a new
  success rate plot.
- Allow the Buildbot master initial start timeout to be configurable.
- An API to check whether an already started instance of a latent worker is
  compatible with what's required by a build that is about to be started.
- Add support for v2 of the Vault key-value secret engine in the
  `SecretInVault` secret provider.

Deprecations and Removals
-------------------------

- Build.canStartWithWorkerForBuilder static method has been made private and
  renamed to _canAcquireLocks.
- The Buildbot master Docker image based on Python 2.7 has been removed in
  favor of a Python 3.7 based image.
- Builder.canStartWithWorkerForBuilder method has been removed. Use
  Builder.canStartBuild.


Buildbot ``1.6.0`` ( ``2018-11-16`` )
=====================================

Bug fixes
---------

- Fixed missing buildrequest owners in the builder page (:issue:`4207`,
  :issue:`3904`)
- Fixed display of the buildrequest number badge text in the builder page when
  on hover.
- Fix usage of master paths when doing Git operations on worker (:issue:`4268`)

Improved Documentation
----------------------

- Misc improvement in Git source build step documentation.
- Improve documentation of AbstractLatentWorker.
- Improve the documentation of the Buildbot concepts by removing unneeded
  details to other pages.

Features
--------

- Added a page that lists all pending buildrequests (:issue:`4239`)
- Builder page now has a chart displaying the evolution of build times over time
- Improved FileUpload efficiency (:issue:`3709`)
- Add method ``getResponsibleUsersForBuild`` in
  :py:class:`~buildbot.notifier.NotifierBase` so that users can override
  recipients, for example to skip authors of changes.
- Add define parameter to RpmBuild to specify additional --define parameters.
- Added SSL proxy capability to base web application's developer test setup
  (``gulp dev proxy --host the-buildbot-host --secure``).

Deprecations and Removals
-------------------------

- The Material design Web UI has been removed as unmaintained. It may be
  brought back if a maintainer steps up.


Buildbot ``1.5.0`` ( ``2018-10-09`` )
=====================================

Bug fixes
---------

- Fix the umask parameter example to make it work with both Python 2.x and 3.x.
- Fix build-change association for multi-codebase builds in the console view..
- Fixed builders page doesn't list workers in multi-master configuration
  (:issue:`4326`)
- Restricted groups added by :py:class:`~buildbot.www.oauth2.GitHubAuth`'s
  ``getTeamsMembership`` option to only those teams to which the user belongs.
  Previously, groups were added for all teams for all organizations to which
  the user belongs.
- Fix 'Show old workers' combo behavior.

Features
--------

- GitHub teams added to a user's ``groups`` by
  :py:class:`~buildbot.www.oauth2.GitHubAuth`'s ``getTeamsMembership`` option
  are now added by slug as well as by name. This means a team named "Bot
  Builders" in the organization "buildbot" will be added as both ``buildbot/Bot
  Builders`` and ``buildbot/bot-builders``.
- Make ``urlText`` renderable for the
  :py:class:`~buildbot.steps.transfer.FileUpload` build step.
- Added ``noticeOnChannel`` option to :bb:reporter:`IRC` to send notices
  instead of messages to channels. This was an option in v0.8.x and removed in
  v0.9.0, which defaulted to sending notices. The v0.8.x default of sending
  messages is now restored.

Reverts
-------

- Reverted: Fix git submodule support when using `sshPrivateKey` and `sshHostKey` because it broke other use cases (:issue:`4316`)
  In order to have this feature to work, you need to keep your master in 1.4.0, and make sure your worker ``buildbot.tac`` are installed in the same path as your master.

Buildbot ``1.4.0`` ( ``2018-09-02`` )
=====================================

Bug fixes
---------

- Fix `Build.getUrl()` to not ignore virtual builders.
- Fix git submodule support when using `sshPrivateKey` and `sshHostKey`
  settings by passing ssh data as absolute, not relative paths.
- Fixed :bb:step:`P4` for change in latest version of `p4 login -p`.
- :py:class:`buildbot.reporters.irc.IrcStatusBot` no longer encodes messages
  before passing them on to methods of its Twisted base class to avoid posting
  the ``repr()`` of a bytes object when running on Python 3.

Features
--------

- Added new :bb:step:`GitPush` step to perform git push operations.
- Objects returned by :ref:`renderer` now are able to pass extra arguments to
  the rendered function via `withArgs` method.

Test Suite
----------

- Test suite has been improved for readability by adding a lot of ``inlineCallbacks``
- Fixed tests which didn't wait for ``assertFailure``'s returned deferred.
- The test suite now runs on Python 3.7 (mostly deprecation warnings from dependencies shut down)

Buildbot ``1.3.0`` ( ``2018-07-13`` )
=====================================

Bug fixes
---------

- buildbot-worker docker image no longer use pidfile. This allows to
  auto-restart a docker worker upon crash.
- GitLab v3 API is deprecated and has been removed from http://gitlab.com, so
  we now use v4. (:issue:`4143`)

Features
--------

- -:bb:step:`Git` now supports `sshHostKey` parameter to specify ssh public
  host key for fetch operations.
- -:bb:step:`Git` now supports `sshPrivateKey` parameter to specify private ssh
  key for fetch operations.
- -:bb:chsrc:`GitPoller` now supports `sshHostKey` parameter to specify ssh
  public host key for fetch operations. This feature is supported on git 2.3
  and newer.
- -:bb:chsrc:`GitPoller` now supports `sshPrivateKey` parameter to specify
  private ssh key for fetch operations. This feature is supported on git 2.3
  and newer.
- Github hook token validation now uses ``hmac.compare_digest()`` for better security

Deprecations and Removals
-------------------------

- Removed support for GitLab v3 API ( GitLab < 9 ).

Buildbot ``1.2.0`` ( ``2018-06-10`` )
=====================================

Bug fixes
---------

- Don't schedule a build when a GitLab merge request is deleted or edited (:issue:`3635`)
- Add GitLab source step; using it, we now handle GitLab merge requests from
  forks properly (:issue:`4107`)
- Fixed a bug in :py:class:`~buildbot.reporters.mail.MailNotifier`'s
  ``createEmail`` method when called with the default *builds* value which
  resulted in mail not being sent.
- Fixed a Github crash that happened on Pull Requests, triggered by Github
  Web-hooks. The json sent by the API does not contain a commit message. In
  github.py this causes a crash, resulting into response 500 sent back to
  Github and building failure.
- Speed up generation of api/v2/builders by an order of magnitude. (:issue:`3396`).

Improved Documentation
----------------------

- Added ``examples/gitlab.cfg`` to demonstrate integrating Buildbot with
  GitLab.

Features
--------

- :ref:`ForceScheduler-Parameters` now support an ``autopopulate`` parameter.
- :ref:`ForceScheduler-Parameters` ``ChoiceParameter`` now correctly supports
  the ``strict`` parameter, by allowing free text entry if strict is False.
- Allow the remote ref to be specified in the GitHub hook configuration (:issue:`3998`)
- Added callable to p4 source that allows client code to resolve the p4 user
  and workspace into a more complete author. Default behaviour is a lambda that
  simply returns the original supplied who. This callable happens after the
  existing regex is performed.


Buildbot ``1.1.2`` ( ``2018-05-15`` )
=====================================

Bug fixes
---------

- fix several multimaster issues by reverting :issue:`3911`. re-opens
  :issue:`3783`. (:issue:`4067`, :issue:`4062`, :issue:`4059`)
- Fix :bb:step:`MultipleFileUpload` to correctly compute path name when worker
  and master are on different OS (:issue:`4019`)
- LDAP bytes/unicode handling has been fixed to work with Python 3. This means
  that LDAP authentication, REMOTE_USER authentication, and LDAP avatars now
  work on Python 3. In addition, an of bounds access when trying to load the
  value of an empty LDAP attribute has been fixed.
- Removing ```no-select``` rules from places where they would prevent the user
  from selecting interesting text. (:issue:`3663`)
- fix ```Maximum recursion depth exceeded`` when lots of worker are trying to
  connect while master is starting or reconfiguring (:issue:`4042`).

Improved Documentation
----------------------

- Document a minimal secure config for the Buildbot web interface.
  (:issue:`4026`)

Features
--------

- The Dockerfile for the buildbot master image has been updated to use Alpine
  Linux 3.7. In addition, the Python requests module has been added to this
  image. This makes GitHub authentication work out of the box with this image.
  (:issue:`4039`)
- New steps for Visual Studio 2017 (VS2017, VC141, and MsBuild141).
- The smoke tests have been changed to use ES2017 async and await keywords.
  This requires that the smoke tests run with Node 8 or higher. Use of async
  and await is recommended by the Protractor team:
  https://github.com/angular/protractor/blob/master/docs/async-await.md
- Allow ``urlText`` to be set on a url linked to a ``DirectoryUpload`` step
  (:issue:`3983`)


Buildbot ``1.1.1`` ( ``2018-04-06`` )
=====================================

Bug fixes
---------

- Fix issue which marked all workers dis-configured in the database every 24h
  (:issue:`3981` :issue:`3956` :issue:`3970`)
- The :bb:reporter:`MailNotifier` no longer crashes when sending from/to email
  addresses with "Real Name" parts (e.g., ``John Doe <john.doe@domain.tld>``).
- Corrected pluralization of text on landing page of the web UI

Improved Documentation
----------------------

- Corrected typo in description of libvirt
- Update sample config to use preferred API

Misc Improvements
-----------------

- Home page now contains links to recently active builders

Buildbot ``1.1.0`` ( ``2018-03-10`` )
=====================================


Deprecations and Removals
-------------------------

- Removed ``ramlfication`` as a dependency to build the docs and run the tests.

Bug fixes
---------

- Fixed buildrequests API doesn't provide properties data (:issue:`3929`)
- Fix missing owner on builder build table (:issue:`3311`)
- Include `hipchat` as reporter.
- Fix encoding issues of commands with Windows workers (:issue:`3799`).
- Fixed Relax builder name length restriction (:issue:`3413`).
- Fix the configuration order so that services can actually use secrets (:issue:`3985`)
- Partially fix Builder page should show the worker information  (:issue:`3546`).

Features
--------

- Added the ``defaultProperties`` parameter to :bb:cfg:`builders`.
- When a build step has a log called "summary" (case-insensitive), the Build
  Summary page will sort that log first in the list of logs, and automatically
  expand it.


Buildbot ``1.0.0`` ( ``2018-02-11`` )
=====================================

Despite the major version bump, Buildbot 1.0.0 does not have major difference with the 0.9 series.
1.0.0 is rather the mark of API stability.
Developers do not foresee a major API break in the next few years like we had for 0.8 to 0.9.

Starting with 1.0.0, Buildbot will follow `semver`_ versioning methodology.

.. _semver: https://semver.org/

Bug fixes
---------

- Cloning :bb:step:`Git` repository with submodules now works with Git < 1.7.6
  instead of failing due to the use of the unsupported ``--force`` option.
- :bb:chsrc:`GitHub` hook now properly creates a change in case of new tag or
  new branch. :bb:chsrc:`GitHub` changes will have the ``category`` set to
  ``tag`` when a tag was pushed to easily distinguish from a branch push.
- Fixed issue with :py:meth:`Master.expireMasters` not always honoring its
  ``forceHouseKeeping`` parameter. (:issue:`3783`)
- Fixed issue with steps not correctly ending in ``CANCELLED`` status when
  interrupted.
- Fix maximum recursion limit issue when transferring large files with
  ``LocalWorker`` (issue:`3014`).
- Added an argument to P4Source that allows users to provide a callable to
  convert Perforce branch and revision to a valid revlink URL. Perforce
  supplies a p4web server for resolving urls into change lists.
- Fixed issue with ``buildbot_pkg``` not hanging on yarn step on windows
  (:issue:`3890`).
- Fix issue with :bb:cfg:`workers` ``notify_on_missing`` not able to be
  configurable as a single string instead of list of string (:issue:`3913`).
- Fixed Builder page should display worker name instead of id (:issue:`3901`).

Features
--------

- Add capability to override the default UI settings (:issue:`3908`)
- All :ref:`Reporters` have been adapted to be able to use :ref:`Secret`.
  :bb:chsrc:`SVNPoller` has been adapted to be able to use :ref:`Secret`.
- Implement support for Bitbucket Cloud webhook plugin in
  :py:class:`~buildbot.www.hooks.bitbucketcloud.BitbucketCloudEventHandler`
- The ``owners`` property now includes people associated with the changes of
  the build (:issue:`3904`).
- The repo source step now syncs with the ``--force-sync`` flag which allows
  the sync to proceed when a source repo in the manifest has changed.
- Add support for compressing the repo source step cache tarball with ``pigz``,
  a parallel gzip compressor.


Older Release Notes
~~~~~~~~~~~~~~~~~~~

.. toctree::
    :maxdepth: 1

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
