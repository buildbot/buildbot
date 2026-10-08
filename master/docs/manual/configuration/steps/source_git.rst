.. bb:step:: Git

.. _Step-Git:

Git
+++

.. py:class:: buildbot.steps.source.git.Git

The :bb:step:`Git` build step clones or updates a `Git <http://git.or.cz/>`_ repository and checks out the specified branch or revision.

.. note::

   Buildbot supports Git version 1.2.0 or later.

.. code-block:: python

   from buildbot.plugins import steps

   factory.addStep(steps.Git(repourl='git://path/to/repo', mode='full',
                             method='clobber', submodules=True))

The Git step takes the following arguments:

``repourl`` (required)
   The URL of the upstream Git repository.

``port`` (optional, default: ``22``)
   The SSH port of the Git server.

``branch`` (optional, default: ``HEAD``)
   This specifies the name of the branch or the tag to use when a Build does not provide one of its own.
   If this parameter is not specified, and the Build does not provide a branch, the default branch of the remote repository will be used.
   If ``alwaysUseLatest`` is ``True`` then the branch and revision information that comes with the Build is ignored and the branch specified in this parameter is used.

``submodules`` (optional, default: ``False``)
   When initializing/updating a Git repository, this tells Buildbot whether to handle Git submodules.
   If ``remoteSubmodules`` is ``True``, then this tells Buildbot to use remote submodules: `Git Remote Submodules <https://git-scm.com/docs/git-submodule#Documentation/git-submodule.txt---remote>`_

``tags`` (optional, default: ``False``)
    Download tags in addition to the requested revision when updating repository.

``shallow`` (optional)
   Instructs Git to attempt shallow clones (``--depth 1``).
   The depth defaults to 1 and can be changed by passing an integer instead of ``True``.
   This option can be used only in incremental builds, or full builds with clobber method.

``reference`` (optional)
   Use the specified string as a path to a reference repository on the local machine.
   Git will try to grab objects from this path first instead of the main repository, if they exist.
   This option is mutually exclusive with ``shared_cache``, which maintains such a repository for you.

``shared_cache`` (optional, default: ``False``)
   When set to ``True``, Buildbot maintains one bare Git object cache per repository on each worker and lets every builder on that worker read objects from it through Git's alternates mechanism.
   Builders that share a worker then stop keeping private copies of the same history, which saves disk space and makes new checkouts faster because most objects are already present locally.
   The cache lives at ``<worker-basedir>/.git-cache/<hash>.git``, where the hash is the first 16 hex digits of the SHA-256 of the cache identity.

   .. code-block:: python

      from buildbot.plugins import steps

      factory.addStep(steps.Git(repourl='https://example.org/repo.git',
                                mode='full', method='fresh',
                                shared_cache=True))

   Enabling the option makes the first build on a worker slower, because Buildbot populates the cache with the repository's full history before the checkout runs.
   The worker needs room for that cache in addition to its existing work directories, which keep the objects they already have.
   A string value specifies a custom cache path instead of the default one.

   This option requires Git 2.12.0 or later.
   On older versions Buildbot does not create, update, or activate a shared cache, and new checkouts use the normal cache-free path.
   If an existing checkout already has a Buildbot-managed alternate from an earlier build, Buildbot preserves it to avoid removing access to borrowed objects, so keep that cache available until the checkout is clobbered or recreated.
   It needs no particular worker version, except that detecting a worker started with ``--delete-leftover-dirs`` requires worker 3.6.0 or later.
   ``shared_cache`` and ``reference`` are mutually exclusive.
   The cache applies only to the top-level repository: submodule object databases and Git LFS payloads are not shared.

   Cache contents and refresh
      New clones use ``--reference`` and existing repositories get a Buildbot-managed entry in ``.git/objects/info/alternates``, recorded alongside it in a ``buildbot-shared-cache`` marker file so Buildbot can tell its own entry from one you added.
      In the cache itself Buildbot records ``buildbot.sharedCacheIdentity`` and the timestamps ``buildbot.sharedCacheLastFsck`` and ``buildbot.sharedCacheFsckFailed``; removing both forces the next build to re-check the cache.
      For an existing linked working tree, Buildbot asks Git for the common object-info directory instead of assuming that ``.git`` is a directory.
      Buildbot creates the cache with ``git init --bare`` and then populates it through its controlled fetch path instead of cloning the upstream repository into the cache.
      This avoids temporarily storing URL userinfo as the cache's ``origin`` and avoids Git clone's local hard-link optimization.
      The cache stores branch heads for the repository and fetches tags only when ``tags=True``.
      The cache always stores full history, so combining it with ``shallow`` still downloads and keeps the complete repository on the worker even though the checkout stays shallow.
      When the build has a revision that the cache already contains, Buildbot skips the cache fetch for that build, so cached branch heads can lag behind the origin; ``tags=True`` disables that skip, because a build may need tags the cache has not fetched yet.
      The requested branch or ref is also fetched, but only through Git's temporary ``FETCH_HEAD`` state; Buildbot does not create a permanent cache ref for each request or checkout.
      The cache itself is always unfiltered, even when the checkout uses ``filters``; a repository already configured as a partial clone is rejected as a cache, preserved, and the build continues without it.

   Validation and failure handling
      Buildbot runs a full ``git fsck --no-dangling`` when the cache has no valid check timestamp or its previous successful check is at least 24 hours old.
      The check runs while the cache lock is held, so on a large cache other builds using the same cache wait for it; a build that waits longer than the step's ``timeout`` continues without the cache.
      The full check is deliberately retained because weaker connectivity-only checks can miss pack corruption, but it is not run on every build.
      A cache that fails the check is not re-checked for another 24 hours, so a corrupt cache costs one check rather than one per build; builds keep running without it in the meantime.
      Whenever a cache cannot be prepared, updated or validated, Buildbot preserves it at its existing path, disables it for the current build, logs the reason, and continues without the cache; it never deletes or replaces an existing cache, and the next build retries, except for the integrity check, which waits for the interval above.
      Only a cache created during the current preparation attempt may be removed, before it is exposed to any checkout.
      An administrator must repair or retire a preserved cache only after migrating or recreating dependent work directories.
      A failed cache-backed clone is retried once without the cache.
      Using ``clobberOnFailure=True`` can recreate an existing checkout without the cache when its fetch fails, but it does not repair or remove an unusable shared cache.
      Buildbot limits each worker-to-master read of its checkout marker and alternates file to 256 KiB.
      If existing metadata exceeds that limit or is not valid UTF-8, Buildbot leaves it unchanged and skips shared-cache alternates management for that checkout.

   Concurrency and maintenance
      Cache preparation, update and validation are serialized per master; the cache lock is released before checkout work begins so builders can use the populated cache concurrently.
      Automatic Git maintenance is disabled for the cache.
      Buildbot does not automatically run Git garbage collection or prune cache objects because existing checkouts may still borrow objects that are otherwise unreachable in the cache.
      Consequently, the cache can grow over time as branches are force-pushed or deleted and additional revisions are fetched.
      Administrators must not prune a live cache while any work directory still references it; recreate those work directories or copy their borrowed objects locally before cleanup.
      Buildbot does not automatically remove cache directories that are no longer selected.
      A worker started with ``--delete-leftover-dirs`` deletes every directory in its base directory that no builder is using, which includes the default cache; Buildbot detects that flag and refuses a cache inside the base directory rather than have it deleted on every reconnect, so configure ``shared_cache`` with an absolute path outside the base directory on such workers.
      Workers from 2.7.0 through 3.5.0 accept the flag but do not report it to the master, so this protection cannot engage for them; on those workers configure an absolute cache path outside the base directory.
      A worker without that flag instead logs a "leftover directory" hint for the cache on every connect; that hint does not apply to the cache, which must not be deleted while any work directory still borrows from it.
      Because the default path is derived from the rendered repository URL, configurations that select many changing URLs, such as source forks, can create multiple caches on one worker.
      The :bb:step:`GitLab` step is the common case: it rewrites ``repourl`` to the source project of each merge request, so a busy project accumulates one cache per contributing fork.
      Cross-fork cache sharing is not supported.
      Remove an unused cache only after all work directories that reference it have been migrated or recreated.

   Checkout alternates and migration
      Existing repositories start using the cache but do not discard objects they already contain, so they do not shrink automatically.
      Clobber or recreate existing work directories to realize the disk savings.
      Buildbot does not replace an existing managed alternate when the configured cache path changes, because that alternate may contain the only copy of objects borrowed by the checkout.
      Existing work directories continue using the old cache until they are clobbered or recreated, so the old cache must remain available during that migration.
      Buildbot matches its managed alternate by literal path text, so configure the worker base directory and any custom cache path with one consistent spelling; an equivalent spelling through a symbolic link, a Windows 8.3 short name, or different letter case is treated as a different path and can require clobbering the checkout as if the cache path had changed.
      Buildbot also preserves an existing managed alternate if cache preparation is temporarily unavailable.
      If an old cache has been deleted or damaged, the checkout may require clobbering before it can continue without it.
      Disabling the option does not remove an entry installed by an earlier build; clobber or recreate the work directory when disabling it.

   Custom cache paths
      Relative custom paths are resolved from the worker base directory; absolute paths are used directly.
      On Windows, relative means a path with neither a drive nor a root.
      Drive-relative paths such as ``C:cache``, current-drive-rooted paths such as ``\cache`` or ``/cache``, and incomplete UNC paths are rejected; use an ordinary relative path, a fully qualified drive path, or a complete UNC path.
      The path identifies one exact bare repository dedicated to Buildbot; it is not a cache root or a general-purpose reference repository.
      When Buildbot creates the repository, it records the cache identity in ``buildbot.sharedCacheOwner``.
      An existing custom repository is accepted only when that ownership marker and its ``origin`` match the computed cache identity.
      An unmarked or mismatched repository is preserved and rejected without modification.
      Buildbot owns an accepted custom repository: it may rewrite its ``origin``, hooks directory and maintenance configuration, fetch and prune its branch heads and optional tags, and update ``FETCH_HEAD``.
      Do not share a custom cache with another consumer.
      Custom paths are trusted worker configuration.
      Configure one consistent path spelling for each custom cache; do not configure paths that resolve through symbolic links to the same repository because the per-master lock is keyed by the normalized configured path rather than the worker's resolved file-system identity.

      The cache must be self-contained.
      Buildbot rejects a cache containing either ``objects/info/alternates`` or ``objects/info/http-alternates`` because checkouts using it would otherwise depend transitively on another object store.

   Cache identity and credentials
      The cache identity uses a lowercase scheme and drops a port that is the default for it, so ``git@host:repo``, ``ssh://git@host/repo`` and ``ssh://git@host:22/repo`` share one cache; other spelling differences, such as a non-default port or a trailing slash, select different caches.
      For HTTP and HTTPS URLs, URL userinfo is removed from the cache identity and the cache's ``origin`` URL.
      For other schemes the username is kept, so ``ssh://alice@host/repo`` and ``ssh://bob@host/repo`` use separate caches.
      Credentials supplied through ``auth_credentials`` or ``git_credentials`` are also not part of the cache identity.
      Consequently, ``shared_cache=True`` makes all credentials used with the same credential-free repository URL share one object store.
      Enabling this mode asserts that those credentials expose the same repository object graph and are permitted to share objects.
      If authentication can expose different objects for the same URL, configure a distinct string ``shared_cache`` path for each credential scope.
      The configured ``repourl`` and credentials are still used for network fetches.
      HTTP and HTTPS repository URLs containing a query or fragment are rejected when shared caching is enabled because Buildbot cannot safely distinguish repository identity parameters from credentials that must not be persisted.
      This restriction does not apply when ``shared_cache`` is disabled.
      Relative local file-system paths are not supported as ``repourl`` when ``shared_cache`` is enabled; use an absolute local path or a repository URL.
      On Windows, a local ``repourl`` must likewise be fully qualified; drive-relative, current-drive-rooted, and incomplete UNC paths are rejected.
      This does not affect relative string values for ``shared_cache`` itself, which are resolved from the worker base directory as described above.

   Isolation
      The cache is not a security boundary between mutually untrusted jobs running as the same worker user.
      The worker's user must own the cache directory: on Unix-like systems Git refuses to operate on a repository owned by another user, in which case Buildbot preserves the cache, disables it for the build, and continues without it.
      Cache Git commands do not inherit the step's ``config`` option and remove repository-scoped Git environment variables, such as ``GIT_DIR`` and the ``GIT_CONFIG`` family, from the step's ``env`` option.
      Variables exported in the worker daemon's own environment are not removed, so do not set repository-scoped Git variables there.
      Buildbot directs cache hooks to an empty cache-specific directory and does not activate the cache if that directory cannot be recreated.

   Windows
      Git commands from a shared-cache step use command-scoped ``core.longpaths=true`` unless the step's ``config`` option sets ``core.longpaths`` explicitly.
      Cache commands run from the local worker base directory and select the cache with ``git -C``, so ``cmd.exe`` is never asked to use a UNC working directory.
      Commands that operate directly on the cache use a command-scoped ``safe.directory`` entry for that cache path.
      A fully qualified local or UNC ``repourl`` is trusted separately through command-scoped ``safe.directory`` entries for both the repository path and its ``.git`` subdirectory, so bare and non-bare source repositories work alike.
      UNC values use Git for Windows' portable ``%(prefix)///server/share/path`` representation.
      These settings do not modify system or global Git configuration.
      ``core.longpaths`` applies to Git commands only; worker-side file transfers and other Python or ``cmd.exe`` operations remain subject to the worker's Windows path support.
      It also does not allow Git to create or enter a repository whose own directory path exceeds the legacy Windows path limit, and the system long-path policy does not lift that either.
      The default cache path adds 32 characters to the worker base directory, so keep the base directory well within that limit; when the cache path is unusable, Buildbot logs the failure and builds continue without the cache.
      A UNC cache also remains subject to the reliability and performance characteristics of its network file system and Git for Windows version.
      Validate a UNC cache against your own Git for Windows release and file server before deploying it.

``origin`` (optional)
   By default, any clone will use the name "origin" as the remote repository (eg, "origin/master").
   This renderable option allows that to be configured to an alternate name.

``filters`` (optional, type: ``list``)
   For each string in the passed in list, adds a ``--filter <filter>`` argument to :command:`git clone` and :command:`git fetch`.
   For existing repositories, Buildbot also configures the remote as a partial clone promisor remote before fetching.
   If that configuration cannot be persisted, the source step fails before starting the filtered fetch.
   Git ignores ``--filter`` for a plain local path and clones fully, printing only a warning; use a ``file://`` URL to keep the filter effective.
   This allows for adding filters like ``--filter "tree:0"`` to speed up clone and fetch operations.
   This requires git version 2.27 or higher.

``progress`` (optional)
   Passes the (``--progress``) flag to (:command:`git fetch`).
   This solves issues of long fetches being killed due to lack of output, but requires Git 1.7.2 or later.
   Its value is True on Git 1.7.2 or later.

``retryFetch`` (optional, default: ``False``)
   If true, if the ``git fetch`` fails, then Buildbot retries to fetch again instead of failing the entire source checkout.

``clobberOnFailure`` (optional, default: ``False``)
   If a fetch or full clone fails, we can retry to checkout the source by removing everything and cloning the repository.
   If the retry fails, it fails the source checkout step.

``mode`` (optional, default: ``'incremental'``)
   Specifies whether to clean the build tree or not.

   ``incremental``
      The source is update, but any built files are left untouched.

   ``full``
      The build tree is clean of any built files.
      The exact method for doing this is controlled by the ``method`` argument.

``method`` (optional, default: ``fresh`` when mode is ``full``)
   Git's incremental mode does not require a method.
   The full mode has four methods defined:

   ``clobber``
      It removes the build directory entirely then makes full clone from repo.
      This can be slow as it need to clone whole repository.
      To make faster clones enable the ``shallow`` option.
      If the shallow option is enabled and the build request has unknown revision value, then this step fails.

   ``fresh``
      This removes all other files except those tracked by Git.
      First it does :command:`git clean -d -f -f -x`, then fetch/checkout to a specified revision (if any).
      This option is equal to update mode with ``ignore_ignores=True`` in old steps.

   ``clean``
      All the files which are tracked by Git, as well as listed ignore files, are not deleted.
      All other remaining files will be deleted before the fetch/checkout.
      This is equivalent to :command:`git clean -d -f -f` then fetch.
      This is equivalent to ``ignore_ignores=False`` in old steps.

   ``copy``
      This first checks out source into source directory, then copies the ``source`` directory to ``build`` directory, and then performs the build operation in the copied directory.
      This way, we make fresh builds with very little bandwidth to download source.
      The behavior of source checkout follows exactly the same as incremental.
      It performs all the incremental checkout behavior in ``source`` directory.

``getDescription`` (optional)
   After checkout, invoke a `git describe` on the revision and save the result in a property; the property's name is either ``commit-description`` or ``commit-description-foo``, depending on whether the ``codebase`` argument was also provided.
   The argument should either be a ``bool`` or ``dict``, and will change how `git describe` is called:

   * ``getDescription=False``: disables this feature explicitly
   * ``getDescription=True`` or empty ``{}``: runs `git describe` with no args
   * ``getDescription={...}``: a dict with keys named the same as the Git option.
     Each key's value can be ``False`` or ``None`` to explicitly skip that argument.

     For the following keys, a value of ``True`` appends the same-named Git argument:

      * ``all`` : `--all`
      * ``always``: `--always`
      * ``contains``: `--contains`
      * ``debug``: `--debug`
      * ``long``: `--long``
      * ``exact-match``: `--exact-match`
      * ``first-parent``: `--first-parent`
      * ``tags``: `--tags`
      * ``dirty``: `--dirty`

     For the following keys, an integer or string value (depending on what Git expects) will set the argument's parameter appropriately.
     Examples show the key-value pair:

      * ``match=foo``: `--match foo`
      * ``exclude=foo``: `--exclude foo`
      * ``abbrev=7``: `--abbrev=7`
      * ``candidates=7``: `--candidates=7`
      * ``dirty=foo``: `--dirty=foo`

``config`` (optional)
   A dict of Git configuration settings to pass to the remote Git commands.

``sshPrivateKey`` (optional)
   The private key to use when running Git for fetch operations.
   The ssh utility must be in the system path in order to use this option.
   On Windows, only Git distribution that embeds MINGW has been tested (as of July 2017, the official distribution is MINGW-based).
   The worker must either have the host in the known hosts file or the host key must be specified via the `sshHostKey` option.

``sshHostKey`` (optional)
   Specifies public host key to match when authenticating with SSH public key authentication.
   This may be either a :ref:`Secret` or just a string.
   `sshPrivateKey` must be specified in order to use this option.
   The host key must be in the form of `<key type> <base64-encoded string>`, e.g. `ssh-rsa AAAAB3N<...>FAaQ==`.

``sshKnownHosts`` (optional)
   Specifies the contents of the SSH known_hosts file to match when authenticating with SSH public key authentication.
   This may be either a :ref:`Secret` or just a string.
   `sshPrivateKey` must be specified in order to use this option.
   `sshHostKey` must not be specified in order to use this option.

``auth_credentials``

   (optional) An username/password tuple to use when running git for fetch operations.
   The worker's git version needs to be at least 1.7.9.

``git_credentials``

   (optional) See :ref:`GitCredentialOptions`.
   The worker's git version needs to be at least 1.7.9.
