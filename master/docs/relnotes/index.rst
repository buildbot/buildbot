Release Notes
~~~~~~~~~~~~~
..
    Buildbot uses towncrier to manage its release notes.
    towncrier helps to avoid the need for rebase when several people work at the same time on the release notes files.

    Each PR should come with a file in the newsfragment directory

.. towncrier release notes start

Buildbot ``4.3.0`` ( ``2025-05-12`` )
=====================================

Bug fixes
---------

- Improved handling of not found exceptions when stopping containers in Docker latent worker.
- Fixed garbage output from ANSI escape code sequences in build step logs (:bug:`7852`)
- Fixed ``AuthorizedKeysManhole`` not picking up the specified ``ssh_host_keydir``
- Fixed deprecation warnings being incorrectly raised as errors
- Fixed Git step failures when checking out commits containing LFS objects that require
  authentication
- Fixed crashes when using callable categories with HgPoller
- :py:class:`~buildbot.reporters.http.HttpStatusPush` now correctly exposes and passes through the
  `skip_encoding` parameter
- Implemented bold text style in build step logs (:issue:`7853`)
- Websocket connections no longer allow unauthenticated users to connect when authorization is
   enabled


Changes
-------

- ``Build`` now has a mutable ``env`` attribute, which is deep copied from the ``Builder``'s
  ``BuilderConfig.env``. This allows steps to modify their current build's environment if needed.


Features
--------

- Added a ``Build.do_build`` field and ``BuilderConfig.do_build_if`` to allow skipping entire builds
- Added support for configuring the database engine via the ``db.engine_kwargs`` configuration key
- Added support for tracking exact commits within codebases
- :py:class:`~buildbot.util.httpclientservice.HTTPSession` now supports mTLS.
  :py:class:`~buildbot.reporters.http.HttpStatusPush` now supports mTLS endpoints by accepting
  client certificates via the `cert` parameter (as either a combined file or tuple)
- Added a ``Log.flush()`` method to flush incomplete log lines without finishing the log
- Added a `runtime_timeout` argument to `MasterShellCommand` :issue:`8377`
- Added a `builds/<buildid>/triggered_builds` Data API endpoint to retrieve builds triggered by
  a specific build


Misc
----

- Added a ``path_cls`` attribute (either ``PureWindowsPath`` or ``PurePosixPath`` depending on
  worker OS). This will replace ``path_module`` usage with better ergonomics and typing support.


Deprecations and Removals
-------------------------

- BuildFactory workdir callable support has been deprecated. Use renderables instead.
- Endpoint.pathPatterns as a multiline string has been deprecated. Use list of strings instead.
- ResourceType.eventPathPatterns as a multiline string has been deprecated. Use list of strings instead.
- DataConnector.produceEvent() has been deprecated. Use Data API update methods as replacement.
- The ``rootlinks`` Data and REST API endpoint has been deprecated
- Buildbot Master now requires Python 3.9 or newer.
  Python 3.8 is no longer supported.
- Raising ``NotImplementedError`` from ``reconfigServiceWithSibling`` or
  ``reconfigService`` has been deprecated. Use ``canReconfigWithSibling()`` that returns ``False`` as
  a replacement.
- ``buildbot.schedulers.base.BaseScheduler`` has been deprecated. Replace uses of it with
  ``ReconfigurableBaseScheduler``.
- Old location of ``Dependent`` scheduler has been deprecated. Instead of
  ``buildbot.schedulers.basic.Dependent`` use ``buildbot.plugins.schedulers.Dependent``.

Buildbot ``4.2.1`` ( ``2025-01-10`` )
=====================================

Bug fixes
---------

- Fixed regression introduced in Buildbot 4.2.0 that broke support for renderable Git step repourl parameter.

Buildbot ``4.2.0`` ( ``2024-12-10`` )
=====================================

Bug fixes
---------

- Fixed an `Access is denied` error on Windows when calling `AssignProcessToJobObject` (:issue:`8162`).
- Improved new build prioritization when many builds arrive at similar time.
- Fixed ``copydb`` script when SQLAlchemy 2.x is used.
- Fixed ``copydb`` script when there are rebuilt builds in the database.
- Fixed ``SetPropertiesFromEnv`` not treating environment variable names as case insensitive for
  Windows workers
- Reliability of Gerrit change source has been improved on unstable connections.
- Fixed bad default of Github webhooks not verifying HTTPS certificates in connections originating from Buildbot.
- Fixed the timestamp comparison in janitor: it should cleanup builds 'older than' given timestamp -
  previously janitor would delete all build_data for builds 'newer than' the configured build data horizon.
- Fixed compatibility with Twisted 24.11.0 due to ``twisted.python.constants`` module being moved.
- Fixed build status reporting to use state_string as fallback when ``status_string`` is ``None``.
  This makes IRC build failure messages more informative by showing the failure reason instead of
  just "failed".
- Fix exception when worker loses connection to master while a command is running.
- Fix certain combinations of ANSI reset escape sequences not displayed correctly (:issue:`8216`).
- Fixed wrong positioning of search box in Buildbot UI log viewer.
- Improved ANSI escape sequence support in Buildbot UI log viewer:
  - Fixed support for formatting and color reset.
  - Fixed support for simultaneous background and foreground color (:issue:`8151`).
- Slightly reduced waterfall view loading times


Improved Documentation
----------------------

- Fixed Scheduler documentation to indicate that owner property is a string, not a list, and
  contains only one owner. This property was changed to singular and to string in Buildbot 1.0,
  but documentation was not updated.


Features
--------

- Use standard URL syntax for Git steps to enable the use of a dedicated SSH port.
- Added ``ignore-fk-error-rows`` option to ``copy-db`` script. It allows ignoring
  all rows that fail foreign key constraint checks. This is useful in cases when
  migrating from a database engine that does not support foreign key constraints
  to one that does.
- Enhanced ``debounce.method`` to support calling target function only when the burst is finished.
- Added support for specifying the master protocol to ``DockerLatentWorker`` and
  ``KubeLatentWorker``. These classes get new ``master_protocol`` argument. The worker
  docker image will receive the master protocol via BUILDMASTER_PROTOCOL environment
  variable.
- Master's ``cleanupdb`` command can now run database optimization on PostgreSQL and MySQL
  (only available on SQLite previously)
- Added a way to setup ``TestReactorMixin`` with explicit tear down function.
- Added a way to return all test result sets from `getTestResultSets()`
  and from data API via new /test_result_sets path.


Misc
----

- Logs compression/decompression operation no longer occur in a Database connection thread.
  This change will improve overall master reactivity on instances receiving large logs from Steps.
- Improve logs compression operation performance with zstd.
  Logs compression/decompression tasks now re-use ``zstandard``'s ``ZstdCompressor`` and
  ``ZstdDecompressor`` objects, as advised in the documentation.
- BuildView's 'Changes' tab (`builders/:builderid/builds/:buildnumber`) now only loads a limited
  number of changes, with the option to load more.
- BuildView (`builders/:builderid/builds/:buildnumber`) now load 'Changes' and 'Responsible Users'
  on first access to the tab. This lower unnecessary queries on the master.


Deprecations and Removals
-------------------------

- The following test tear down functions have been deprecated:

   - ``TestBuildStepMixin.tear_down_test_build_step()``
   - ``TestReactorMixin.tear_down_test_reactor()``

  The tear down is now run automatically. Any additional test tear down should be run using
  ``twisted.trial.TestCase.addCleanup`` to better control tear down ordering.

- ``Worker.__init__`` no longer accepts ``usePTY`` argument. It has been deprecated for a long time
  and no other values than ``None`` were accepted.

Buildbot ``4.1.0`` ( ``2024-10-13`` )
=====================================

Bug fixes
---------

- Fixed crash in ``GerritEventLogPoller`` when invalid input is passed (:issue:`7612`)
- Fixed ``Build`` summary containing non obfuscated ``Secret`` values present in a failed
  ``BuildStep`` summary (:issue:`7833`)
- Fixed data API query using buildername to correctly work with buildername containing spaces and
  unicode characters (:issue:`7752`)
- Fixed an error when master is reconfigured with new builders and a build finishing at this time,
  causing the build to never finish.
- Fixed crash on master shutdown trying to insubstantiate build's worker when no worker is assigned
  to the build (:issue:`7753`)
- Fixed confusing error messages in case of HTTP errors that occur when connecting to Gerrit server.
- Fixed ``GitPoller`` merge commit processing. ``GitPoller`` now correctly list merge commit files.
  (:issue:`7494`)
- Fixed hang in ``buildbot stop --clean`` when a in progress build was waiting on a not yet started
  BuildRequest that it triggered.
- Improved error message in case of OAuth2 failures.
- Fixed display of navigation links when the web frontend is displayed in narrow window (:issue:`7818`)
- Fixed inconsistent logs data in reports produced by report generators. In particular, ``stepname``
  key is consistently attached to logs regardless if they come with build steps or with the global
  ``logs`` key.
- Fixed a regression where a ``ChoiceStringParameter`` requires a user selected
  value (no default value), but the force build form incorrectly displays the
  first choice as being selected which later causes validation error.
- Fixed logs ``/raw`` and ``/raw_inline`` endpoint requiring large memory on master (more than full log size)
  (:issue:`3011`)
- Fixed sidebar group expander to use different icon for expanded groups.
- Log queries in BuildView (``builders/:builderid/builds/:buildnumber``) have been reduced when
  logs won't be displayed to the user.
- REST API json responses now correctly provide the ``Content-Length`` header for non-HEAD requests.
- Buildbot is now compatible with SQLAlchemy v2.0+

Changes
-------

- Buildbot will now add a trailing '/' to the ``buildbotURL`` and ``titleURL`` configured values if it
  does not have one.
- The internal API presented by the database connectors has been changed to return data classes
  instead of Python dictionaries. For backwards compatibility the classes also support being
  accessed as dictionaries. The following functions have been affected:

  - ``BuildDataConnectorComponent`` ``getBuildData``, ``getBuildDataNoValue``, and ``getAllBuildDataNoValues``
    now return a ``BuildDataModel`` instead of a dictionary.
  - ``BuildsConnectorComponent`` ``getBuild``, ``getBuildByNumber``, ``getPrevSuccessfulBuild``,
    ``getBuildsForChange``, ``getBuilds``, ``_getRecentBuilds``, and ``_getBuild`` now return a ``BuildModel``
    instead of a dictionary.
  - ``BuildRequestsConnectorComponent`` ``getBuildRequest``, and ``getBuildRequests`` now return a
    ``BuildRequestModel`` instead of a dictionary.
  - ``BuildsetsConnectorComponent`` ``getBuildset``, ``getBuildsets``, and ``getRecentBuildsets`` now
    return a ``BuildSetModel`` instead of a dictionary.
  - ``BuildersConnectorComponent`` ``getBuilder`` and ``getBuilders`` now return a ``BuilderModel`` instead
    of a dictionary.
  - ``ChangesConnectorComponent`` ``getChange``, ``getChangesForBuild``, ``getChangeFromSSid``, and
    ``getChanges`` now return a ``ChangeModel`` instead of a dictionary.
  - ``ChangeSourcesConnectorComponent`` ``getChangeSource``, and ``getChangeSources`` now return a
    ``ChangeSourceModel`` instead of a dictionary.
  - ``LogsConnectorComponent`` ``getLog``, ``getLogBySlug``, and ``getLogs`` now return a ``LogModel``
    instead of a dictionary.
  - ``MastersConnectorComponent`` ``getMaster``, and ``getMasters`` now return a ``MasterModel`` instead
    of a dictionary.
  - ``ProjectsConnectorComponent`` ``get_project``, ``get_projects``, and ``get_active_projects`` now
    return a ``ProjectModel`` instead of a dictionary.
  - ``SchedulersConnectorComponent`` ``getScheduler``, and ``getSchedulers`` now return a
    ``SchedulerModel`` instead of a dictionary.
  - ``SourceStampsConnectorComponent`` ``getSourceStamp``, ``get_sourcestamps_for_buildset``,
    ``getSourceStampsForBuild``, and ``getSourceStamps`` now return a ``SourceStampModel`` instead of a
    dictionary.
  - ``StepsConnectorComponent`` ``getStep``, and ``getSteps`` now return a ``StepModel`` instead of a
    dictionary.
  - ``TestResultsConnectorComponent`` ``getTestResult``, and ``getTestResults`` now return a
    ``TestResultModel`` instead of a dictionary.
  - ``TestResultSetsConnectorComponent`` ``getTestResultSet``, and ``getTestResultSets`` now return
    a ``TestResultSetModel`` instead of a dictionary.
  - ``UsersConnectorComponent`` ``getUser``, ``getUserByUsername``, and ``getUsers`` now return a
    ``UserModel`` instead of a dictionary.
  - ``WorkersConnectorComponent`` ``getWorker``, and ``getWorkers`` now return a ``WorkerModel`` instead
    of a dictionary.
- ``Git`` step no longer includes ``-t`` (tags) option when fetching by default. Explicitly enabling
  with ``tags=True`` is now required to achieve the same functionality.
- ``logCompressionMethod`` will default to ``zstd`` if the ``buildbot[zstd]`` extra set was
  installed (otherwise, it default to ``gzip`` as before).
- Buildbot now requires ``treq`` package to be installed.
- Buildbot worker will now run process in ``JobObject`` on Windows, so child processes can be killed
  if main  process dies itself either intentionally or accidentally.
- Worker docker image now uses Debian 12.
- Settings UI has been improved by reducing group header size and adding space between groups.

Features
--------

- ``copy-db`` script now reads/writes in parallel and in batches. This results in it being faster
  and having smaller memory footprint
- Added possibility to set ``START_TIMEOUT`` via environment variable.
- Added data API ``/workers/n:workerid/builders`` allowing to query the Builders assigned to a worker
- The ``db_url`` config value can now be a renderable, allowing usage of secrets from secrets providers.
  eg. ``util.Interpolate("postgresql+psycopg2://db_user:%(secret:db_password)s@db_host:db_port/db_name")``
- Added ``tooltip`` parameter to the forcescheduler, allowing passing help text to web frontend
  to explain the user what the parameters mean.
- ``Git`` and ``GitPush`` steps and ``GitPoller`` change source now support authentication with
  username/password. Credentials can be provided through the ``auth_credentials`` and/or
  ``git_credentials`` parameters.
- ``Git`` step ``getDescription`` configuration now supports the first-parent and exclude arguments.
- ``Git`` step now honors the shallow option in fetching in addition to clone and submodules.
- Github change hooks how have access to ``full_name`` of the repository when rendering GitHub
  tokens.
- Implemented simpler way to perform HTTP requests via ``httpclientservice.HTTPSession``. It does
  not require a parent service.
- ``logCompressionMethod`` can now be set to ``br`` (using brotli, requires the ``buildbot[brotli]``
  extra) or ``zstd`` (using zstandard, requires the ``buildbot[zstd]`` extra)
- Buildbot now compress REST API responses with the appropriate ``accept-encoding`` header is set.
  Available encodings are: gzip, brotli (requires the ``buildbot[brotli]`` extra), and zstd
  (requires the ``buildbot[zstd]`` extra)
- Added ``max_lines`` parameter to the shell command, allowing processes to be terminated if they
  exceed a specified line count.
- The ``want_logs_content`` argument of message formatters now supports being passed a list of logs
  for which to load the content.
- Exposed log URLs as ``url``, ``url_raw``, ``url_raw_inline`` in the log dictionary generated by
  report generators.
- ``TestBuildStepMixin`` now supports testing multiple steps added via ``setup_step()`` in a single
  unit test.
- Worker base directory has been exposed as a normal build property called ``basedir``.
- Show build and step start and stop times when hovering on duration in build step table.
- The following website URLs now support receiving ``buildername`` instead of ``builderid`` to
  select the builder: ``builders/:builderid``, ``builders/:builderid/builds/:buildnumber``, and
  ``builders/:builderid/builds/:buildnumber/steps/:stepnumber/logs/:logslug``.
- Human readable time is now shown in addition to timestamp in various debug tabs in the web frontend.
- ``ChoiceStringParameter`` can now have both ``multiple=True`` and ``strict=False`` allowing to
  create values in the web UI.
- Buildrequests tables in various places in the web UI now have a button to load more items.
- Added a way to configure sidebar menu group expand behavior in web frontend.
- Web UI's Worker view (``workers/{workerId}``) now has a ``Builders`` tab showing Builders
  configured on the worker
- Builders view now paginates builders list. Page size can be configured with the setting
  'Builders page related settings > Number of builders to show per page'.
- Workers view now paginates workers list. Page size can be configured with the setting
  'Workers page related settings > Number of workers to show per page'.
- Workers view now includes a search box to filter on worker's name.

Deprecations and Removals
-------------------------

- Buildbot worker no longer supports Python 3.4, 3.5 and 3.6. Older version of Buildbot worker should
  be used in case it needs to run on these old versions of Python. Old versions of Buildbot worker
  are fully supported by Buildbot master.
- ``buildbot.db.test_results.TestResultDict`` is deprecated in favor of ``buildbot.db.test_results.TestResultModel``.
- ``buildbot.db.test_result_sets.TestResultSetDict`` is deprecated in favor of ``buildbot.db.test_result_sets.TestResultSetModel``.
- ``buildbot.db.buildrequests.BrDict`` is deprecated in favor of ``buildbot.db.buildrequests.BuildRequestModel``.
- ``buildbot.db.build_data.BuildDataDict`` is deprecated in favor of ``buildbot.db.build_data.BuildDataModel``.
- ``buildbot.db.changes.ChDict`` is deprecated in favor of ``buildbot.db.changes.ChangeModel``.
- ``buildbot.db.masters.MasterDict`` is deprecated in favor of ``buildbot.db.masters.MasterModel``.
- ``buildbot.db.sourcestamps.SsDict`` is deprecated in favor of ``buildbot.db.sourcestamps.SourceStampModel``.
- ``buildbot.db.users.UsDict`` is deprecated in favor of ``buildbot.db.users.UserModel``.
- The following methods of ``httpclientservice.HTTPClientService`` have been deprecated:
  ``get``, ``delete``, ``post``, ``put``, ``updateHeaders``. Use corresponding methods from ``HTTPSession``.
- The ``add_logs`` argument of ``BuildStatusGenerator``, ``BuildStartEndStatusGenerator`` and
  ``BuildSetStatusGenerator`` has been removed. As a replacement, set ``want_logs_content`` of the
  passed message formatter.
- The ``build_files``, ``worker_env`` and ``worker_version`` arguments of
  ``TestBuildStepMixin.setup_step()`` have been deprecated. As a replacement, call
  ``TestBuildStepMixin.setup_build()`` before ``setup_step``.
- The ``step`` attribute of ``TestBuildStepMixin`` has been deprecated. As a replacement, call
  ``TestBuildStepMixin.get_nth_step()``.
- Master running with Twisted >= 24.7.0 does not work with buildbot-worker 0.8.
  Use Twisted 24.3.0 on master if you need to communicate with buildbot-worker 0.8. This may be
  fixed in the future.
- Buildbot master now requires Twisted 22.1.0 or newer.


Buildbot ``4.0.4`` ( ``2024-10-12`` )
=====================================

Bug fixes
---------

- Fixed missing builder force scheduler route ``/builders/:builderid/force/:scheduler``.
- Fixed URL of WGSI dashboards to keep backward compatibility with the old non-React WSGI plugin.
- Fixed display of long property values by wrapping them
- Dropped no longer needed dependency on the ``future`` library

Buildbot ``4.0.3`` ( ``2024-09-27`` )
=====================================

Bug fixes
---------

- Fixed function signature for `CustomAuth.check_credentials`.
- Fixed ReactUI authentication when Buildbot is hosted behind a reverse proxy not at url's root. (:issue:`7814`)
- Made Tags column in Builders page take less space when there are no tags
- Fixed cropped change author avatar image in web UI.
- Fixed pluralization of build count in build summaries in the web UI.
- The change details page no longer requires an additional mouse click to show the change details.
- Fixed showing misleading "Loading" spinner when a change has no builds.
- Fixed too small spacing in change header text in web UI.
- Fixed showing erroneous zero changes count in the web UI when loading changes.
- Cleaned up build and worker tabs in builders view in web UI.
- Fixed links to external URLs in the about pages.
- Fixed missing warnings on old browsers.
- Builds in the home page are now sorted to show the latest one first.
- Fixed loading of plugins settings (e.g. from master's `ui_default_config`)
- Improved visual separation between pending build count and build status in trigger build steps in web UI.

Changes
-------

- Buildbot has migrated to `quay.io` container registry for storing released container images.
  In order to migrate to the new registry container image name in `FROM` instruction in Dockerfiles
  needs to be adjusted to `quay.io/buildbot/buildbot-master` or `quay.io/buildbot/buildbot-worker`.
- GitHubStatusPush will now render github tokens right before the request.
  This allow to update the token in the configuration file without restarting the server,
  which is useful for Github App installations where tokens are rotated every hour.
- The list of supported browsers has been updated to Chrome >=80, Firefox >= 80, Edge >=80,
  Safari >= 14, Opera >=67.

Features
--------

- The text displayed in build links is now configurable and can use any build property.
  It was showing build number or branch and build number before.
- Changes and builds tables in various places in the web UI now have a button to load more items.

Buildbot ``4.0.2`` ( ``2024-08-01`` )
=====================================

Bug fixes
---------

- Fixed ``GitPoller`` when repourl has the port specified (:issue:`7822`)
- Fixed ``ChoiceStringParameter`` fields with ``multiple`` would not store the selected values
- Fixed unnecessary trimming of spaces in logs showed in the web UI (:issue:`7774`)
- Fixed favicon colors on build views in the web UI
- Fixed the icon on the about page in the web UI
- Fixed a regression where builds in waterfall view were no longer linking to the build page.
- Fixed an issue that would cause non-ui www plugins to not be configured (such as buildbot-badges) (:issue:`7665`)

Changes
-------

- Buildbot will now error when configured with multiple services of the same type are configured
  with the same name (:issue:`6987`)

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
