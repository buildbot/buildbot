Release Notes
~~~~~~~~~~~~~
..
    Don't write to this file anymore!!

    Buildbot now uses towncrier to manage its release notes.
    towncrier helps to avoid the need for rebase when several people work at the same time on the releasenote files.

    Each PR should come with a file in the master/buildbot/newsfragment directory

.. towncrier release notes start

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
