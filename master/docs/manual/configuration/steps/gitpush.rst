.. bb:step:: GitPush

.. _Step-GitPush:

GitPush
+++++++

.. py:class:: buildbot.steps.source.git.GitPush

The :bb:step:`GitPush` build step pushes new commits to a `Git <http://git.or.cz/>`_ repository.

The GitPush step takes the following arguments:

``workdir``
    (required) The path to the local repository to push commits from.

``repourl``
    (required) The URL of the upstream Git repository.

``branch``
    (required) The branch to push.
    The branch should already exist on the local repository.

``force``
    (optional) If ``True``, forces overwrite of refs on the remote repository.
    Corresponds to the ``--force`` flag of the ``git push`` command.

``logEnviron``
    (optional) If this option is true (the default), then the step's logfile will describe the environment variables on the worker.
    In situations where the environment is not relevant and is long, it may be easier to set ``logEnviron=False``.

``env``
    (optional) A dictionary of environment strings which will be added to the child command's environment.
    The usual property interpolations can be used in environment variable names and values - see :ref:`Properties`.

``timeout``
    (optional) Specifies the timeout for worker-side operations, in seconds.
    If your repositories are particularly large, then you may need to increase this  value from its default of 1200 (20 minutes).

``config``

    (optional) A dict of git configuration settings to pass to the remote git commands.

``sshPrivateKey``

    (optional) The private key to use when running git for fetch operations.
    The ssh utility must be in the system path in order to use this option.
    On Windows only git distribution that embeds MINGW has been tested (as of July 2017 the official distribution is MINGW-based).
    The worker must either have the host in the known hosts file or the host key must be specified via the ``sshHostKey`` option.

``sshHostKey``

    (optional) Specifies public host key to match when authenticating with SSH public key authentication.
    This may be either a :ref:`Secret` or just a string.
    ``sshPrivateKey`` must be specified in order to use this option.
    The host key must be in the form of ``<key type> <base64-encoded string>``, e.g. ``ssh-rsa AAAAB3N<...>FAaQ==``.

``sshKnownHosts`` (optional)
   Specifies the contents of the SSH known_hosts file to match when authenticating with SSH public key authentication.
   This may be either a :ref:`Secret` or just a string.
   `sshPrivateKey` must be specified in order to use this option.
   `sshHostKey` must not be specified in order to use this option.
