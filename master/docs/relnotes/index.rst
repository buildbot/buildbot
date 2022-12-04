Release Notes
~~~~~~~~~~~~~
..
    Buildbot uses towncrier to manage its release notes.
    towncrier helps to avoid the need for rebase when several people work at the same time on the release notes files.

    Each PR should come with a file in the newsfragment directory

.. towncrier release notes start

Buildbot ``3.7.0`` ( ``2022-12-04`` )
=====================================

Bug fixes
---------

- Improved statistics capture to avoid negative build duration.
- Improved reliability of "buildbot stop" (:issue:`3535`).
- Cancelled builds now have stop reason included into the state string.
- Fixed ``custom_class`` change hook checks to allow hook without a plugin.
- Added treq response wrapper to fix issue with missing url attribute.
- Fixed Buildbot Worker being unable to start on Python 2.7 due to issue in a new version of Automat dependency.

Features
--------

- Expanded ``ChangeFilter`` filtering capabilities:
   - New ``<attribute>_not_eq`` parameters to require no match
   - ``<attribute>_re`` now support multiple regexes
   - New ``<attribute>_not_re`` parameters to require no match by regex
   - New ``property_<match_type>`` parameters to perform filtering on change properties.
- Exposed frontend configuration as implementation-defined JSON document that can be queried separately.
- Added support for custom branch keys to ``OldBuildCanceller``.
  This is useful in Version Control Systems such as Gerrit that have multiple branch names for the same logical branch that should be tracked by the canceller.
- ``p4port`` argument of the ``P4`` step has been marked renderable.
- Added automatic generation of commands for Telegram bot without need to send them manually to BotFather.

Deprecations and Removals
-------------------------

- This release includes an experimental web UI written using React framework.
  The existing web UI is written using AngularJS framework which is no longer maintained.
  The new web UI can be tested by installing ``buildbot-www-react`` package and ``'base_react': {}`` key-value to www plugins.
  Currently no web UI plugins are supported.
  The existing web UI will be deprecated on subsequent Buildbot released and eventually replaced with the React-based web UI on Buildbot 4.0.


Buildbot ``3.6.1`` ( ``2022-09-22`` )
=====================================

Bug fixes
---------

- Fixed handling of last line in logs when Buildbot worker 3.5 and older connects to Buildbot master 3.6 (:issue:`6632`).
- Fixed worker ``cpdir`` command handling when using PB protocol (:issue:`6539`)


Buildbot ``3.6.0`` ( ``2022-08-25`` )
=====================================

Bug fixes
---------

- Fixed compatibility with Autobahn 22.4.x.
- Fixed a circular import that causes errors in certain cases.
- Fixed issue with :bb:worker:`DockerLatentWorker` accumulating connections with the docker server (:issue:`6538`).
- Fixed documentation build for ReadTheDocs: Sphinx and Python have been updated to latest version.
- Fixed build pending and canceled status reports to GitLab.
- Fixed compatibility of hvac implementation with Vault 1.10.x (:issue:`6475`).
- Fixed a race condition in ``PyLint`` step that may lead to step throwing exceptions.
- Reporters now always wait for previous report to completing upload before sending another one.
  This works around a race condition in GitLab build reports ingestion pipeline (:issue:`6563`).
- Fixed "retry fetch" and "clobber on failure" git checkout options.
- Improved Visual Studio installation path retrieval when using MSBuild and only 'BuildTools' are installed.
- Fixed search for Visual Studio executables by inspecting both ``C:\Program Files`` and ``C:\Program Files (x86)`` directories.
- Fixed Visual Studio based steps causing an exception in ``getResultSummary`` when being skipped.
- Fixed issue where workers would immediately retry login on authentication failure.
- Fixed sending emails when using Twisted 21.2 or newer (:issue:`5943`)

Features
--------

- Implemented support for App password authentication in ``BitbucketStatusPush`` reporter.
- Cancelled build requests now generate build reports.
- Implemented support for ``--no-verify`` git option to the ``GitCommit`` step.
- ``HTTPClientService`` now accepts full URL in its methods.
  Previously only a relative URL was supported.
- Callback argument of class ``LineBoundaryFinder`` is now optional and deprecated.
- Added ``VS2019``, ``VS2022``, ``MsBuild15``, ``MsBuild16``, ``MsBuild17`` steps.
- Names of transfer related temporary files are now prefixed with ``buildbot-transfer-``.
- ``buildbot try`` now accepts empty diffs and prints a warning instead of rejecting the diff.
- Implemented note event handling in GitLab www hook.

Deprecations and Removals
-------------------------

- Removed support for Python 3.6 from master.
  Minimal python version for the master is now 3.7.
  The Python version requirements for the worker don't change: 2.7 or 3.4 and newer.
- ``buildbot`` package now requires Twisted versions >= 18.7.0


Buildbot ``3.5.0`` ( ``2022-03-06`` )
=====================================

Bug fixes
---------

- Improved handling of "The container operating system does not match the host operating system" error on Docker on Windows to mark the build as erroneous so that it's not retried.
- Fixed rare ``AlreadyCalledError`` exceptions in the logs when worker worker connection is lost at the same time it is delivering final outcome of a command.
- Fixed errors when accessing non-existing build via REST API when an endpoint matching rule with builder filter was present.
- Fixed an error in ``CMake`` passing options and definitions on the cmake command line.
- Fixed an error when handling command management errors on the worker side (regression since v3.0.0).
- Fixed updating build step summary with mock state changes for MockBuildSRPM and MockRebuild.
- Fixed support for optional ``builder`` parameter used in RebuildBuildEndpointMatcher (:issue:`6307`).
- Fixed error that caused builds to become stuck in building state until next master restart if builds that were in the process of being interrupted lost connection to the worker.
- Fixed Gerrit change sources to emit changes with proper branch name instead of one containing ``refs/heads/`` as the prefix.
- Fixed handling of ``build_wait_timeout`` on latent workers which previously could result in latent worker being shut down while a build is running in certain scenarios (:issue:`5988`).
- Fixed problem on MySQL when using master names or builder tags that differ only by case.
- Fixed timed schedulers not scheduling builds the first time they are enabled with ``onlyIfChanged=True`` when there are no important changes.
  In such case the state of the code is not known, so a build must be run to establish the baseline.
- Switched Bitbucket OAuth client from the deprecated 'teams' APIs to the new 'workspaces' APIs
- Fixed errors when killing a process on a worker fails due to any reason (e.g. permission error or process being already exited) (:issue:`6140`).
- Fixed updates to page title in the web UI.
  Web UI now shows the configured buildbot title within the page title.

Improved Documentation
----------------------

- Fixed brackets in section `2.4.2.4 - How to populate secrets in a build` (:issue:`6417`).

Features
--------

- The use of Renderables when constructing payload For `JSONStringDownload` is now allowed.
- Added ``alwaysPull`` support when using ``dockerfile`` parameter of ``DockerLatentWorker``.
- Base Debian image has been upgraded to Debian Bullseye for the Buildbot master.
- Added rendering support to ``docker_host`` and ``hostconfig`` parameters of ``DockerLatentWorker``.
- ``MailNotifier`` reporter now sends HTML messages by default.
- ``MessageFormatter`` will now use a default subject value if one is not specified.
- The default templates used in message formatters have been improved to supply more information.
  Separate default templates for html messages have been provided.
- Added ``buildbot_title``, ``result_names`` and ``is_buildset`` keys to the data passed to ``MessageFormatter`` instances for message rendering.
- Added ``target`` support when using ``dockerfile`` parameter of ``DockerLatentWorker``.
- Simplified :bb:cfg:`prioritizeBuilders` default function to make an example easier to customize.
- Buildbot now exposes its internal framework for writing tests of custom build steps.
  Currently the API is experimental and subject to change.
- Implemented detection of too long step and builder property names to produce errors at config time if possible.

Deprecations and Removals
-------------------------

- Deprecated ``subject`` argument of ``BuildStatusGenerator`` and ``BuildSetStatusGenerator`` status generators.
  Use ``subject`` argument of corresponding message formatters.


Buildbot ``3.4.1`` ( ``2022-02-09`` )
=====================================

Bug fixes
---------

- Updated Bitbucket API URL for ``BitbucketPullrequestPoller``.
- Fixed a crash in ``BitbucketPullrequestPoller`` (:issue:`4153`)
- Fixed installation of master and worker as Windows service from wheel package (regression since 3.4.0)  (:issue:`6294`)
- Fixed occasional exceptions when using Visual Studio steps (:issue:`5698`).
- Fixed rare "Did you maybe forget to yield the method" errors coming from the log subsystem.


Buildbot ``3.4.0`` ( ``2021-10-15`` )
=====================================

Bug fixes
---------

- Database migrations are now handled using Alembic (1.6.0 or newer is required) (:issue:`5872`).
- AMI for latent worker is now set before making spot request to enable dynamically setting AMIs for instantiating workers.
- Fixed ``GitPoller`` fetch commands timing out on huge repositories
- Fixed a bug that caused Gerrit review comments sometimes not to be reported.
- Fixed a critical bug in the ``MsBuild141`` step (regression since Buildbot v2.8.0) (:issue:`6262`).
- Implemented renderable support in secrets list of ``RemoveWorkerFileSecret``.
- Fixed issues that prevented Buildbot from being used in Setuptools 58 and newer due to dependencies failing to build (:issue:`6222`).

Improved Documentation
----------------------

- Fixed help text for ``buildbot create-master`` so it states that ``--db`` option is passed verbatim to ``master.cfg.sample`` instead of ``buildbot.tac``.
- Added documentation of properties available in the formatting context that is presented to message formatters.

Features
--------

- MsBuild steps now handle correctly rebuilding or cleaning a specific project.
  Previously it could only be done on the entire solution.
- Implemented support for controlling ``filter`` option of ``git clone``.
- Optimized build property filtering in the database instead of in Python code.
- Implemented support of ``SASL PLAIN`` authentication to ``IRC`` reporter.
- The ``want_logs`` (previously ``wantLogs``) argument to message formatters will now imply ``wantSteps`` if selected.
- Added information about log URLs to message formatter context.
- Implemented a way to ask for only logs metadata (excluding content) in message formatters via ``want_logs`` and ``want_logs_content`` arguments.
- Implemented support for specifying pre-processor defines sent to the compiler in the ``MsBuild`` steps.
- Introduced ``HvacKvSecretProvider`` to allow working around flaws in ``HashiCorpVaultSecretProvider`` (:issue:`5903`).
- Implemented support for proxying worker connection through a HTTP proxy.

Deprecations and Removals
-------------------------

- The ``wantLogs`` argument of message formatters has been deprecated.
  Please replace any uses with both ``want_logs`` and ``want_logs_content`` set to the same value.
- The ``wantProperties`` and ``wantSteps`` arguments of message formatters have been renamed to ``want_properties`` and ``want_steps`` respectively.
- Buildbot now requires SQLAlchemy 1.3.0 or newer.


Buildbot ``3.3.0`` ( ``2021-07-31`` )
=====================================

Bug fixes
---------

- Fixed support of SQLAlchemy v1.4 (:issue:`5992`).
- Improved default build request collapsing functionality to take into account properties set by the scheduler and not collapse build requests if they differ (:issue:`4686`).
- Fixed a race condition that would result in attempts to complete unclaimed buildrequests (:issue:`3762`).
- Fixed a race condition in default buildrequest collapse function which resulted in two concurrently submitted build requests potentially being able to cancel each other (:issue:`4642`).
- The ``comment-added`` event on Gerrit now produces the same branch as other events such as ``patchset-created``.
- ``GerritChangeSource`` and ``GerritEventLogPoller`` will now produce change events with ``branch`` attribute that corresponds to the actual git branch on the repository.
- Fixed handling of ``GitPoller`` state to not grow without bounds and eventually exceed the database field size. (:issue:`6100`)
- Old browser warning banner is no longer shown for browsers that could not be identified (:issue:`5237`).
- Fixed worker lock handling that caused max lock count to be ignored (:issue:`6132`).

Features
--------

- Buildbot can now be configured (via ``FailingBuildsetCanceller``) to cancel unfinished builds when a build in a buildset fails.
- ``GitHubEventHandler`` can now configure authentication token via Secrets management for GitHub instances that do not allow anonymous access
- Buildbot can now be configured (via ``OldBuildCanceller``) to cancel unfinished builds when branches on which they are running receive new commits.
- Buildbot secret management can now be used to configure worker passwords.
- Services can now be forced to reload their code via new ``canReconfigWithSibling`` API.

Deprecations and Removals
-------------------------

- ``changes.base.PollingChangeSource`` has been fully deprecated as internal uses of it were migrated to replacement APIs.


Buildbot ``3.2.0`` ( ``2021-06-17`` )
=====================================

Bug fixes
---------

- Fixed occasional ``InvalidSpotInstanceRequestID.NotFound`` errors when using spot instances on EC2.
  This could have lead to Buildbot launching zombie instances and not shutting them down.
- Improved ``GitPoller`` behavior during reconfiguration to exit at earliest possible opportunity and thus reduce the delay that running ``GitPoller`` incurs for the reconfiguration.
- The docker container for the master now fully builds the www packages.
  Previously they were downloaded from pypi which resulted in downloading whatever version was newest at the time (:issue:`4998`).
- Implemented time out for master-side utility processes (e.g. ``git`` or ``hg``) which could break the respective version control poller potentially indefinitely upon hanging.
- Fixed a regression in the ``reconfig`` script which would time out instead of printing error when configuration update was not successfully applied.
- Improved buildbot restart behavior to restore the worker paused state (:issue:`6074`)
- Fixed support for binary patch files in try client (:issue:`5933`)
- Improved handling of unsubscription errors in WAMP which will no longer crash the unsubscribing component and instead just log an error.
- Fixed a crash when a worker is disconnected from a running build that uses worker information for some of its properties (:issue:`5745`).

Improved Documentation
----------------------

- Added documentation about installation Buildbot worker as Windows service.

Features
--------

- ``DebPbuilder`` now supports the ``--othermirror`` flag for including additional repositories
- Implemented support for setting docker container's hostname
- The libvirt latent worker will now wait for the VM to come online instead of disabling the worker during connection establishment process.
  The VM management connections are now pooled by URI.
- Buildbot now sends metadata required to establish connection back to master to libvirt worker VMs.
- ``LibVirtWorker`` will now setup libvirt metadata with details needed by the worker to connect back to master.
- The docker container for the master has been switched to Debian.
  Additionally, buildbot is installed into a virtualenv there to reduce chances of conflicts with Python packages installed via ``dpkg``.
- BitbucketStatusPush now has renderable build status key, name, and description.
- Pausing a worker is a manual operation which the quarantine timer was overwriting. Worker paused state and quarantine state are now independent. (:issue:`5611`)
- Reduce buildbot_worker wheel package size by 40% by dropping tests from package.

Deprecations and Removals
-------------------------

- The `connection` argument of the LibVirtWorker constructor has been deprecated along with the related `Connection` class.
  Use `uri` as replacement.
- The ``*NewStyle`` build step aliases have been removed.
  Please use equivalent steps without the ``NewStyle`` suffix in the name.
- Try client no longer supports protocol used by Buildbot older than v0.9.


Buildbot ``3.1.1`` ( ``2021-04-28`` )
=====================================

Bug fixes
---------

- Fix missing VERSION file in buildbot_worker wheel package (:issue:`5948`, :issue:`4464`).
- Fixed error when attempting to specify ``ws_ping_interval`` configuration option (:issue:`5991`).


Buildbot ``3.1.0`` ( ``2021-04-05`` )
=====================================

Bug fixes
---------

- Fixed usage of invalid characters in temporary file names by git-related steps (:issue:`5949`)
- Fixed parsing of URLs of the form https://api.bitbucket.org/2.0/repositories/OWNER/REPONAME in BitbucketStatusPush.
  These URLs are in the sourcestamps returned by the Bitbucket Cloud hook.
- Brought back the old (pre v2.9.0) behavior of the ``FileDownload`` step to act
  more gracefully by returning ``FAILURE`` instead of raising an exception when the file doesn't exist
  on master. This makes use cases such as ``FileDownload(haltOnFailure=False)`` possible again.
- Fixed issue with ``getNewestCompleteTime`` which was returning no completed builds, although it could.
- Fixed the ``Git`` source step causing last active branch to point to wrong commits.
  This only affected the branch state in the local repository, the checked out code was correct.
- Improved cleanup of any containers left running by ``OpenstackLatentWorker``.
- Improved consistency of log messages produced by the reconfig script.
  Note that this output is not part of public API of Buildbot and may change at any time.
- Improved error message when try client cannot create a build due to builder being not configured on master side.
- Fixed exception when submitting builds via try jobdir client when the branch was not explicitly specified.
- Fixed handling of secrets in nested folders by the vault provider.

Features
--------

- Implemented report generator for new build requests
- Allow usage of Basic authentication to access GitHub API when looking for avatars
- Added support for default Pylint message that was changed in v2.0.
- Implemented support for configurable timeout in the reconfig script via new ``progress_timeout`` command-line parameter which determines how long it waits between subsequent progress updates in the logs before declaring a timeout.
- Implemented ``GitDiffInfo`` step that would extract information about what code has been changed in a pull/merge request.
- Add support ``--submodule`` option for the ``repo init`` command of the Repo source step.

Deprecations and Removals
-------------------------

- ``MessageFormatter`` will receive the actual builder name instead of ``whole buildset`` when used from ``BuildSetStatusGenerator``.


Buildbot ``3.0.3`` ( ``2021-04-05`` )
=====================================

Bug fixes
---------

- Fixed a race condition in log handling of ``RpmLint`` and ``WarningCountingShellCommand`` steps resulting in steps crashing occasionally.
- Fixed incorrect state string of a finished buildstep being sent via message queue (:issue:`5906`).
- Reduced flickering of build summary tooltip during mouseover of build numbers (:issue:`5930`).
- Fixed missing data in Owners and Worker columns in changes and workers pages (:issue:`5888`, :issue:`5887`).
- Fixed excessive debug logging in ``GerritEventLogPoller``.
- Fixed regression in pending buildrequests UI where owner is not displayed anymore (:issue:`5940`).
- Re-added support for ``lazylogfiles`` argument of ``ShellCommand`` that was available in old style steps.

Buildbot ``3.0.2`` ( ``2021-03-16`` )
=====================================

Bug fixes
---------

- Updated Buildbot requirements to specify sqlalchemy 1.4 and newer as not supported yet.


Buildbot ``3.0.1`` ( ``2021-03-14`` )
=====================================

Bug fixes
---------

- Fixed special character handling in avatar email URLs.
- Fixed errors when an email address matches GitHub commits but the user is unknown to it.
- Added missing report generators to the Buildbot plugin database (:issue:`5892`)
- Fixed non-default mode support for ``BuildSetStatusGenerator``.


Buildbot ``3.0.0`` ( ``2021-03-08`` )
=====================================

This release includes all changes up to Buildbot ``2.10.2``.

Bug fixes
---------

- Avatar caching is now working properly and size argument is now handled correctly.
- Removed display of hidden steps in the build summary tooltip.
- ``GitHubPullrequestPoller`` now supports secrets in its ``token`` argument (:issue:`4921`)
- Plugin database will no longer issue warnings on load, but only when a particular entry is accessed.
- SSH connections are now run with ``-o BatchMode=yes`` to prevent interactive prompts which may tie up a step, reporter or change source until it times out.

Features
--------

- ``BitbucketPullrequestPoller``, ``BitbucketCloudEventHandler``, ``BitbucketServerEventHandler`` were enhanced to save PR entries matching provided masks as build properties.
- ``BitbucketPullrequestPoller`` has been enhanced to optionally authorize Bitbucket API.
- Added `pullrequesturl` property to the following pollers and change hooks: ``BitbucketPullrequestPoller``, ``GitHubPullrequestPoller``, ``GitHubEventHandler``.
  This unifies all Bitbucket and GitHub pollers with the shared property interface.
- AvatarGitHub class has been enhanced to handle avatar based on email requests and take size argument into account
- Added support for Fossil user objects for use by the buildbot-fossil plugin.
- A new ``www.ws_ping_interval`` configuration option was added to avoid websocket timeouts when using reverse proxies and CDNs (:issue:`4078`)

Deprecations and Removals
-------------------------

- Removed deprecated ``encoding`` argument to ``BitbucketPullrequestPoller``.
- Removed deprecated support for constructing build steps from class and arguments in ``BuildFactory.addStep()``.
- Removed support for deprecated ``db_poll_interval`` configuration setting.
- Removed support for deprecated ``logHorizon``, ``eventHorizon`` and ``buildHorizon`` configuration settings.
- Removed support for deprecated ``nextWorker`` function signature that accepts two parameters instead of three.
- Removed deprecated ``status`` configuration setting.
- ``LoggingBuildStep`` has been removed.
- ``GET``, ``PUT``, ``POST``, ``DELETE``, ``HEAD``, ``OPTIONS`` steps now use new-style step implementation.
- ``MasterShellCommand`` step now uses new-style step implementation.
- ``Configure``, ``Compile``, ``ShellCommand``, ``SetPropertyFromCommand``, ``WarningCountingShellCommand``, ``Test`` steps now use new-style step implementation.
- Removed support for old-style steps.
- Python 3.5 is no longer supported for running Buildbot master.
- The deprecated ``HipChatStatusPush`` reporter has been removed.
- Removed support for the following deprecated parameters of ``HttpStatusPush`` reporter: ``format_fn``, ``builders``, ``wantProperties``, ``wantSteps``, ``wantPreviousBuild``, ``wantLogs``, ``user``, ``password``.
- Removed support for the following deprecated parameters of ``BitbucketStatusPush`` reporter: ``builders``, ``wantProperties``, ``wantSteps``, ``wantPreviousBuild``, ``wantLogs``.
- Removed support for the following deprecated parameters of ``BitbucketServerStatusPush``, ``BitbucketServerCoreAPIStatusPush``, ``GerritVerifyStatusPush``, ``GitHubStatusPush``, ``GitHubCommentPush`` and ``GitLabStatusPush`` reporters: ``startDescription``, ``endDescription``, ``builders``, ``wantProperties``, ``wantSteps``, ``wantPreviousBuild``, ``wantLogs``.
- Removed support for the following deprecated parameters of ``BitbucketServerPRCommentPush``, ``MailNotifier``, ``PushjetNotifier`` and ``PushoverNotifier`` reporters: ``subject``, ``mode``, ``builders``, ``tags``, ``schedulers``, ``branches``, ``buildSetSummary``, ``messageFormatter``, ``watchedWorkers``, ``messageFormatterMissingWorker``.
- Removed support for the following deprecated parameters of ``MessageFormatter`` report formatter: ``template_name``.
- The deprecated ``send()`` function that can be overridden by custom reporters has been removed.
- Removed deprecated support for ``template_filename``, ``template_dir`` and ``subject_filename`` configuration parameters of message formatters.
- The deprecated ``buildbot.status`` module has been removed.
- The deprecated ``MTR`` step has been removed.
  Contributors are welcome to step in, migrate this step to newer APIs and add a proper test suite to restore this step in Buildbot.
- Removed deprecated ``buildbot.test.fake.httpclientservice.HttpClientService.getFakeService()`` function.
- Removed deprecated support for ``block_device_map`` argument of EC2LatentWorker being not a list.
- Removed support for deprecated builder categories which have been replaced by tags.


Older Release Notes
~~~~~~~~~~~~~~~~~~~

.. toctree::
    :maxdepth: 1

    2.x
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
