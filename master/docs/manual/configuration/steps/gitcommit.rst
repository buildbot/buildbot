.. bb:step:: GitCommit

.. _Step-GitCommit:

GitCommit
+++++++++

.. py:class:: buildbot.steps.source.git.GitCommit

The :bb:step:`GitCommit` build step adds files and commits modifications in your local `Git <http://git.or.cz/>`_ repository.

The GitCommit step takes the following arguments:

``workdir``
    (required) The path to the local repository to push commits from.

``messages``
    (required) List of message that will be created with the commit.
    Correspond to the ``-m`` flag of the ``git commit`` command.

``paths``
    (required) List of path that will be added to the commit.

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

``no_verify``
    (optional) Specifies whether ``--no-verify`` option should be supplied to git.
    The default is ``False``.

``emptyCommits``
    (optional) One of the values ``disallow`` (default), ``create-empty-commit``, and ``ignore``. Decides the behavior when there is nothing to be committed.
    The value ``disallow`` will make the buildstep fail.
    The value ``create-empty-commit`` will create an empty commit.
    The value ``ignore`` will create no commit.
