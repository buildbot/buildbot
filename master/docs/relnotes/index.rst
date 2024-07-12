Release Notes
~~~~~~~~~~~~~
..
    Buildbot uses towncrier to manage its release notes.
    towncrier helps to avoid the need for rebase when several people work at the same time on the release notes files.

    Each PR should come with a file in the newsfragment directory

.. towncrier release notes start

Buildbot ``4.0.1`` ( ``2024-07-12`` )
=====================================

Bug fixes
---------

- Transfer build steps (:bb:step:`FileUpload`, :bb:step:`DirectoryUpload`,
  :bb:step:`MultipleFileUpload`, :bb:step:`FileDownload`, and :bb:step:`StringDownload`) now
  correctly remove destination on failure, no longer leaving partial content (:issue:`2860`)
- Fixed ReactUI when Buildbot is hosted behind a reverse proxy not at url's root (:issue:`7260`,
  :issue:`7746`)
- Fixed results color shown on builder's header in waterfall view
- Fixed cases where waterfall view could be squashed to a pixel high
- Improved flexibility of ``scaling_waterfall`` setting to support floating-point values for more
  condensed view.
- Fixed broken theming in web frontend when not using it via ``base_react`` plugin name.
- Fixed ``/builders/n:builderid/builds/n:build_number/properties`` endpoint returning results
  for wrong builds.
- Fixed useless logged ``fatal Exception on DB: log with slug ... already exists in this step``
  errors.

Buildbot ``4.0.0`` ( ``2024-06-24`` )
======================================

Bug fixes
---------

- ``BitbucketServerCoreAPIStatusPush`` now handles epoch time format in events as well as `datetime.datetime`.
- Fixed buildrequest cancel requests being ignored under certain infrequent conditions.
- Fixed an issue in lock handling which caused step locks to be acquired in excess of their
  configured capacity under certain conditions (:issue:`5655`, :issue:`5987`).
- ``OldBuildCanceller`` will now cancel builds only if a superseding buildrequest is actually
  created. Previously it was enough to observe a superseding change even if it did not result in
  actually running builds.
- Fixed ``OldBuildCanceller`` crashes when sourcestamp with no branch was ingested.
- Fixed ``ChoiceStringParameter`` fields being not present in ForceBuild Form.
- Fixed initialization of default web setting values from config.
- Fixed loading of user saved settings in React web frontend.

Changes
-------

- Added optional ``locks_acquired_at`` argument to ``master.data.updates.set_step_locks_acquired_at()``.
- Master and Worker packages have stopped using the deprecated ``distutils`` package and rely on
  setuptools. Worker installation now requires setuptools.
- Events between ``GerritChangeSource`` and ``GerritEventLogPoller`` are no longer deduplicated.
  Use ``GerritChangeSource`` with both SSH and HTTP API configured as a replacement.
- ``GitPoller`` no longer track the ``master`` branch when neither ``branch`` nor ``branches``
  arguments are provided. It now track the remote's default branch.
- Improved performance of ``OpenstackWorker`` startup when there are large number of images on the server.
- ``buildbot.www.plugin.Application`` no longer accepts module name as the first parameter.
  It requires the name of package. In most cases where ``__name__`` was being passed, ``__package__``
  is now required.
- Padding of the UI elements in the web UI has been reduced to increase density of presented data.
- Buildbot now requires SQLAlchemy 1.4.0 or newer.
- Old ``importlib_resources`` is no longer used.

Features
--------

- Added ``rebuilt_buildid`` key-value pair to buildsets to be able to keep track on which build is
  being rebuild.
- Buildbot now tracks total time that has been spent waiting for locks in a build.
- Added ``projectid`` and ``projectname`` properties to Build
- The ``worker_preparation`` dummy step that tracks various build startup overhead has been split
  into two steps to track worker startup and locks wait times separately.
- Builds now have ``builderid`` property.
- Build request cancellation has been exposed to the Data API.
- Added optional ``started_at`` and ``locks_acquired`` arguments to ``master.data.updates.startStep()``.
- ``buildbot.test.fake.httpclientservice.HTTPClientService`` now can simulate network and processing
  delays via ``processing_delay_s`` option to ``expect()`` method.
- Added ability to poll HTTP event API of Gerrit server to ``GerritChangeSource``. This has the
  following advantages compared to simply pointing ``GerritChangeSource`` and
  ``GerritEventLogPoller`` at the same Gerrit server:

    - All events are properly deduplicated
    - SSH connection is restarted in case of silent hangs of underlying SSH connection (this may
      happen even when ServerAliveInterval is used)

- Added ``select_next_worker`` global configuration key which sets default ``nextWorker``
  customization hook on all builders.
- Added support for connecting Kubernetes workers to multiple Kubernetes clusters.
- Raw logs downloaded from the web UI now include full identifying information in the filename.
- Raw text logs downloaded from the web UI now include a small header with identifying information.
- The Rebuild button on a Build's view now redirect to the Buildrequest corresponding to the latest rebuild.
- Add a "Workers" tab to the Builder view listing workers that are assigned to this builder (:issue:`7162`)
- Added check for correct argument types to ``BuildStep`` and ``ShellCommand`` build steps and all steps
  deriving from ``ShellMixin``. This will avoid wrong arguments causing confusing errors in unrelated
  parts of the codebase.
- Implemented a check for step attempting to acquire the same lock as its build.
- Implement support for customizing ``affinity`` and ``nodeSelector`` fields in Kubernetes pod spec
  for Kubernetes worker.
- The debug tab in build page now shows previous build that has been built on the same worker
  for the same builder. This helps debugging any build directory cleanup problems in custom Buildbot
  setups.
- Add support for case insensitive search within the logs.
- Add support for regex search within the logs.


Deprecations and Removals
-------------------------

- ``buildbot.process.factory.Distutils`` factory has been deprecated.
- ``HashiCorpVaultSecretProvider`` has been removed.
- ``GerritStatusPush`` no longer accepts deprecated arguments: ``reviewCB``, ``startCB``,
  ``reviewArg``, ``startArg``, ``summaryCB``, ``summaryArg``, ``builders``, ``wantSteps``,
  ``wantLogs``.
- Deprecated module-level attributes have been deleted.
- ``GerritStatusPush`` callback functions now can only return dictionary type.
- AngularJS web frontend has been removed.
- Deprecated ``LineBoundaryFinder callback`` argument has been removed.
- Removed Python 2.7 support on the worker. This does not affect compatibility of connecting workers
  running old versions of Buildbot to masters running new versions of Buildbot.

This release includes all changes up to Buildbot 3.11.5.

Older Release Notes
~~~~~~~~~~~~~~~~~~~

.. toctree::
    :maxdepth: 1

    3.x
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
