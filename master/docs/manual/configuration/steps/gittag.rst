.. bb:step:: GitTag

.. _Step-GitTag:

GitTag
++++++

.. py:class:: buildbot.steps.source.git.GitTag

The :bb:step:`GitTag` build step creates a tag in your local `Git <http://git.or.cz/>`_ repository.

The GitTag step takes the following arguments:

``workdir``
    (required) The path to the local repository to push commits from.

``tagName``
    (required) The name of the tag.

``annotated``
    (optional) If ``True``, create an annotated tag.

``messages``
    (optional) List of message that will be created with the annotated tag.
    Must be set only if annotated parameter is ``True``.
    Correspond to the ``-m`` flag of the ``git tag`` command.

``force``
    (optional) If ``True``, forces overwrite of tags on the local repository.
    Corresponds to the ``--force`` flag of the ``git tag`` command.

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
