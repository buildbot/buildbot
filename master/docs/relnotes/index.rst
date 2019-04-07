Release Notes
~~~~~~~~~~~~~
..
    Don't write to this file anymore!!

    Buildbot now uses towncrier to manage its release notes.
    towncrier helps to avoid the need for rebase when several people work at the same time on the releasenote files.

    Each PR should come with a file in the master/buildbot/newsfragment directory

.. towncrier release notes start

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


Buildbot ``0.9.15.post1`` ( ``2018-01-07`` )
============================================

Bug fixes
---------

- Fix worker reconnection fails (:issue:`3875`, :issue:`3876`)
- Fix umask set to 0 when using LocalWorker (:issue:`3878`)
- Fix Buildbot reconfig, when badge plugin is installed (:issue:`3879`)
- Fix (:issue:`3865`) so that now
  :py:class:`~buildbot.changes.svnpoller.SVNPoller` works with paths that
  contain valid UTF-8 characters which are not ASCII.


Buildbot ``0.9.15`` ( ``2018-01-02`` )
======================================

Bug fixes
---------

- Fix builder page not showing any build (:issue:`3820`)
- Fix double Workers button in the menu. (:issue:`3818`)
- Fix bad icons in the worker action dialog.
- Fix url arguments in Buildbot :ref:`Badges` for python3.
- Upgrading to `guanlecoja-ui` version 1.8.0, fixing two issues. Fixed issue
  where the console view would jump to the top of page when opening the build
  summary dialog (:issue:`3657`). Also improved sidebar behaviour by remembering
  previous pinned vs. collapsed state.
- Fixes issue with Buildbot :bb:worker:`DockerLatentWorker`, where Buildbot can kill running
  workers by mistake based on the form the worker name (:issue:`3800`).
- Fixes issue with Buildbot :bb:worker:`DockerLatentWorker` not reaping zombies process within its container environment.
- Update requirement text to use the modern "docker" module from the older
  "docker-py" module name
- When multiple :bb:cfg:`reporter` or :bb:cfg:`services` are configured with
  the same name, an error is now displayed instead of silently discarding all
  but the last one :issue:`3813`.
- Fixed exception when using :py:class:`buildbot.www.auth.CustomAuth`

Features
--------

- New Buildbot SVG icons for web UI. The web UI now uses a colored favicon
  according to build results (:issue:`3785`).
- ``paused`` and ``graceful`` :ref:`Worker-states` are now stored in the
  database.
- :ref:`Worker-states` are now displayed in the web UI.
- Quarantine timers is now using the ``paused`` worker state.
- Quarantine timer is now enabled when a build finish on ``EXCEPTION`` state.
- Standalone binaries for buildbot-worker package are now published for windows and linux (``amd64``).
  This allows to run a buildbot-worker without having a python environment.
- New ``buildbot-worker create-worker --maxretries`` for :ref:`Latent-Workers`
  to quit if the master is or becomes unreachable.
- Badges can now display `running` as status.
- The database schema now supports cascade deletes for all objects instead of
  raising an error when deleting a record which has other records pointing to
  it via foreign keys.
- Buildbot can properly find its version if installed from a git archive tarball generated from a tag.
- Enhanced the test suite to add worker/master protocol interoperability tests between python3 and python2.

Deprecations and Removals
-------------------------

- buildbot.util.ascii2unicode() is removed. buildbot.util.bytes2unicode()
  should be used instead.


Buildbot ``0.9.14`` ( ``2017-12-08`` )
======================================

Bug fixes
---------

- Compile step now properly takes the decodeRC parameter in account
  (:issue:`3774`)
- Fix duplicate build requests results in
  :py:class:`~buildbot.db.buildrequests.BuildRequestsConnectorComponent` when
  querying the database (:issue:`3712`).
- :py:class:`~buildbot.changes.gitpoller.GitPoller` now accepts git branch
  names with UTF-8 characters (:issue:`3769`).
- Fixed inconsistent use of `pointer` style mouse cursor by removing it from
  the `.label` css rule and instead creating a new `.clickable` css rule which
  is used only in places which are clickable and would not otherwise
  automatically get the `pointer` icon, for example it is not needed for
  hyper-links. (:issue:`3795`).
- Rebuilding with the same revision now takes new change properties into
  account instead of re-using the original build change properties
  (:issue:`3701`).
- Worker authentication is now delayed via a DeferredLock until Buildbot
  configuration is finished. This fixes UnauthorizedLogin errors during
  buildbot restart (:issue:`3462`).
- Fixes python3 encoding issues with Windows Service (:issue:`3796`)

Features
--------

- new :ref`badges` plugin which reimplement the buildbot eight png badge
  system.
- In progress worker control API. Worker can now be stopped and paused using the UI.
  Note that there is no UI yet to look the status of those actions (:issue:`3429`).
- Make maximum number of builds fetched on the builders page configurable.
- Include `context` in the log message for `GitHubStatusPush`
- On 'Builders' page reload builds when tags change.
- Give reporters access to master single in renderables. This allows access to
  build logs amongst other things
- Added possibility to check www user credentials with a custom class.


Buildbot ``0.9.13`` ( ``2017-11-07`` )
======================================

Deprecations and Removals
-------------------------

Following will help Buildbot to leverage new feature of twisted to implement important features like worker protocol encryption.

- The ``buildbot`` and ``buildbot-worker`` packages now requires Python 2.7 or
  Python 3.4+ -- Python 2.6 is no longer supported.
- ``buildbot`` and ``buildbot-worker`` packages now required Twisted versions
  >= 16.1.0. Earlier versions of Twisted are not supported.

Bug fixes
---------

- Fix Console View forced builds stacking at top (issue:`3461`)
- Improve buildrequest distributor to ensure all builders are processed. With
  previous version, builder list could be re-prioritized, while running the
  distributor, meaning some builders would never be run in case of master high
  load. (:issue:`3661`)
- Improve ``getOldestRequestTime`` function of buildrequest distributor to do
  sorting and paging in the database layer (:issue:`3661`).
- Arguments passed to GitLab push notifications now work with Python 3 (:issue:`3720`).
- Web hooks change sources which use twisted.web.http.Request have been fixed to use bytes, not
  native strings. This ensures web hooks work on Python 3. Please report any issues on web hooks in python3, as it is hard for us to test end to end.
- Fixed null value of steps and logs in reporter HttpStatusPush api. Fixes
  (:issue:`3180`)
- EC2LatentBuilder now correctly sets tags on spot instances (:issue:`3739`).
- Fixed operation of the Try scheduler for a code checked out from Subversion.
- Fix buildbot worker startup when running as a windows service

Features
--------

- Make parameters for
  :py:class:`~buildbot.steps.shell.WarningCountingShellCommand` renderable.
  These are `suppressionList`, `warningPattern`, `directoryEnterPattern`,
  `directoryLeavePattern` and `maxWarnCount`.
- :py:class:`~buildbot.www.hooks.github.GitHubEventHandler` now supports
  authentication for GitHub instances that do not allow anonymous access
- Added support for renderable builder locks. Previously only steps could have
  renderable locks.
- Added flag to Docker Latent Worker to always pull images


Buildbot ``0.9.12.post1`` ( ``2017-10-10`` )
============================================

This is a release which only exists for the ``buildbot_grid_view`` package.

Bug fixes
---------
- Fix Grid View plugin broken because of merge resolution mistake ( :issue:`3603` and :issue:`3688`.)

Buildbot ``0.9.12`` ( ``2017-10-05`` )
======================================

Bug fixes
---------

- Fixed many issues related to connecting masters and workers with different major version of Python (:issue:`3416`).
- Fixed KeyError in the log when two buildrequests of the same buildset are finished at the same time (:issue:`3472`, :issue:`3591`)
- Fix for SVN.purge fails when modified files contain non-ascii characters (:issue:`3576`)
- Fix the GitHub change hook on Python 3 (:issue:`3452`).
- Fix :class:`reporters.gitlab` to use correct commit status codes (:issue:`3641`).
- Fixed deadlock issue, when locks are taken at least 3 times by the 3 Buildstep with same configuration (:issue:`3650`)
- Fix the Gerrit source step in the presence of multiple Gerrit repos (:issue:`3460`).
- Add empty pidfile option to master and worker start script when `--nodaemon` option is on. (:issue:`3012`).

Features
--------

- Add possibility to specify a :bb:sched:`PatchParameter` for any :bb:sched:`CodebaseParameter` in a :bb:sched:`ForceScheduler` (part of :issue:`3110`).
- Latent Workers will no longer continually retry if they cannot substantiate (:issue:`3572`)

Deprecations and Removals
-------------------------

- buildbot.util.encodeString() has been removed. buildbot.util.unicode2bytes() should be used instead.


Buildbot ``0.9.11`` ( ``2017-09-08`` )
======================================

Incompatible Changes
--------------------

- Buildbot is not compatible with ``python3-ldap`` anymore. It now requires ``ldap3`` package for its ldap operations (:issue:`3530`)

Bug fixes
---------

- Fix issue with ``logviewer`` scrolling up indefinitely when loading logs
  (:issue:`3154`).
- Do not add the url if it already exists in the step. (:issue:`3554`)
- Fix filtering for REST resource attributes when SQL is involved in the backend (eq, ne, and
  contains operations, when there are several filters) (:issue:`3526`).
- The ``git`` source step now uses `git checkout -B` rather than `git branch -M` to create local branches (:issue:`3537`)
- Fixed :ref:`Grid View <GridView>` settings. It is now possible to configure "false" values.
- Fix performance issue when remote command does not send any line boundary
  (:issue:`3517`)
- Fix regression in GithHub oauth2 v3 api, when using enterprise edition.
- Fix the Perforce build step on Python 3 (:issue:`3493`)
- Make REST API's filter __contains use OR connector rather than AND according
  to what the documentation suggests.
- Fixed secret plugins registration, so that they are correctly available in ``import buildbot.plugins.secrets``.
  changes to all secrets plugin to be imported and used.
- Fix secrets downloaded to worker with too wide permissions.
- Fix issue with stop build during latent worker substantiating, the build result
  was retried instead of cancelled.
- ``pip install 'buildbot[bundle]'`` now installs ``grid_view`` plugin.
  This fixes issues with the tutorial where ``grid_view`` is enabled by default.

Improved Documentation
----------------------

- Fixed documentation regarding log obfuscation for passwords.
- Improve documentation of REST API's __contains filter.

Features
--------

- Added autopull for Docker images based on config. (:issue:`3071`)
- Allow to expose logs to summary callback of :py:class:`GerritStatusPush`.
- Implement GitHub change hook CI skipping (:issue:`3443`). Now buildbot will
  ignore the event, if the ``[ci skip]`` keyword (configurable) in commit
  message. For more info, please check out the ``skip`` parameter of
  :bb:chsrc:`GitHub` hook.
- :py:class:`~buildbot.reporters.github.GitHubStatusPush` now support reporting
  to ssh style URLs, ie `git@github.com:Owner/RepoName.git`
- Added the possibility to filter builds according to results in :ref:`Grid
  View <GridView>`.
- :py:class:`~buildbot.worker.openstack.OpenStackLatentWorker` now supports V3
  authentication.
- Buildbot now tries harder at finding line boundaries. It now supports several
  cursor controlling ANSI sequences as well as use of lots of backspace to go
  back several characters.
- UI Improvements so that Buildbot build pages looks better on mobile.
- :py:class:`~buildbot.worker.openstack.OpenStackLatentWorker` now supports
  region attribute.
- The :ref:`Schedulers` ``builderNames`` parameter can now be a
  :class:`~IRenderable` object that will render to a list of builder names.
- The :py:class:`~buildbot.www.ldapuserinfo.LdapUserInfo` now uses the
  python3-ldap successor ldap3 (:issue:`3530`).
- Added support for static suppressions parameter for shell commands.


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
