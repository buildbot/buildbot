Release Notes
~~~~~~~~~~~~~
..
    Don't write to this file anymore!!

    Buildbot now uses towncrier to manage its release notes.
    towncrier helps to avoid the need for rebase when several people work at the same time on the releasenote files.

    Each PR should come with a file in the master/buildbot/newsfragment directory

.. towncrier release notes start

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
