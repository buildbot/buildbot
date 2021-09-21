.. bb:step:: Git

.. _Step-Git:

Git
+++

.. py:class:: buildbot.steps.source.git.Git

The :bb:step:`Git` build step clones or updates a `Git <http://git.or.cz/>`_ repository and checks out the specified branch or revision.

.. note::

   Buildbot supports Git version 1.2.0 or later. Earlier versions (such as the one shipped in Ubuntu 'Dapper') do not support the :command:`git init` command that Buildbot uses.

.. code-block:: python

   from buildbot.plugins import steps

   factory.addStep(steps.Git(repourl='git://path/to/repo', mode='full',
                             method='clobber', submodules=True))

The Git step takes the following arguments:

``repourl`` (required)
   The URL of the upstream Git repository.

``branch`` (optional)
   This specifies the name of the branch or the tag to use when a Build does not provide one of its own.
   If this parameter is not specified, and the Build does not provide a branch, the default branch of the remote repository will be used.
   If ``alwaysUseLatest`` is ``True`` then the branch and revision information that comes with the Build is ignored and the branch specified in this parameter is used.

``submodules`` (optional, default: ``False``)
   When initializing/updating a Git repository, this tells Buildbot whether to handle Git submodules.
   If ``remoteSubmodules`` is ``True``, then this tells Buildbot to use remote submodules: `Git Remote Submodules <https://git-scm.com/docs/git-submodule#Documentation/git-submodule.txt---remote>`_

``shallow`` (optional)
   Instructs Git to attempt shallow clones (``--depth 1``).
   The depth defaults to 1 and can be changed by passing an integer instead of ``True``.
   This option can be used only in full builds with clobber method.

``reference`` (optional)
   Use the specified string as a path to a reference repository on the local machine.
   Git will try to grab objects from this path first instead of the main repository, if they exist.

``origin`` (optional)
   By default, any clone will use the name "origin" as the remote repository (eg, "origin/master").
   This renderable option allows that to be configured to an alternate name.

``filters`` (optional, type: ``list``)
   For each string in the passed in list, adds a ``--filter <filter>`` argument to :command:`git clone`.
   This allows for adding filters like ``--filter "tree:0"`` to speed up the clone step.
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
   * ``getDescription=True`` or empty ``dict()``: runs `git describe` with no args
   * ``getDescription={...}``: a dict with keys named the same as the Git option.
     Each key's value can be ``False`` or ``None`` to explicitly skip that argument.

     For the following keys, a value of ``True`` appends the same-named Git argument:

      * ``all`` : `--all`
      * ``always``: `--always`
      * ``contains``: `--contains`
      * ``debug``: `--debug`
      * ``long``: `--long``
      * ``exact-match``: `--exact-match`
      * ``tags``: `--tags`
      * ``dirty``: `--dirty`

     For the following keys, an integer or string value (depending on what Git expects) will set the argument's parameter appropriately.
     Examples show the key-value pair:

      * ``match=foo``: `--match foo`
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
