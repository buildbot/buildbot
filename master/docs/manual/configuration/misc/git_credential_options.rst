.. _GitCredentialOptions:

GitCredentialOptions
++++++++++++++++++++

.. py:class:: buildbot.util.GitCredentialOptions

The following parameters are supported by the :py:class:`GitCredentialOptions`:


``credentials``
    (optional, a list of strings)
    Each element of the list must be in the `git-credential input format <https://git-scm.com/docs/git-credential#IOFMT>`_
    and will be passed as input to ``git credential approve``.

``use_http_path``
    (optional, a boolean)
    If provided, will set the `credential.useHttpPath <https://git-scm.com/docs/gitcredentials#Documentation/gitcredentials.txt-useHttpPath>`_
    configuration to it's value for commands that require credentials.

Examples
~~~~~~~~

.. code-block:: python

    from buildbot.plugins import util

    factory.addStep(steps.Git(
        repourl='https://example.com/hello-world.git', mode='incremental',
        git_credentials=util.GitCredentialOptions(
            credentials=[
                (
                    "url=https://example.com/hello-world.git\n"
                    "username=username\n"
                    "password=token\n"
                ),
            ],
        ),
    ))
