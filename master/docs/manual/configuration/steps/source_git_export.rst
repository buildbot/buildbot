.. bb:step:: GitExport

.. _Step-GitExport:

GitExport
+++++++++

.. py:class:: buildbot.steps.source.git.GitExport

The :bb:step:`GitExport` build step exports a path from a Git repository without
cloning the complete repository. It uses the remote ``git-upload-archive``
service and extracts the resulting tar archive into the step's ``workdir``.

.. code-block:: python

   from buildbot.plugins import steps, util

   factory.addStep(
       steps.GitExport(
           repourl='ssh://git@example.com/project.git',
           path='src/component',
           branch='main',
           sshPrivateKey=util.Secret('git-ssh-key'),
       )
   )

The GitExport step takes the following arguments:

``repourl`` (required)
   The URL of the upstream Git repository.

``path`` (required)
   A repository-relative subtree path, using forward slashes. The exported
   files retain this path as a directory beneath ``workdir``. If that directory
   already exists in ``workdir``, it is removed before extraction so files
   deleted from the repository do not remain in the export.

``branch`` (optional, default: ``'HEAD'``)
   The branch or tag to export when the build does not provide a revision.
   ``got_revision`` is set to the commit resolved for the export.

``port`` (optional, default: ``22``)
   The SSH port of the Git server.

``config`` (optional)
   A dict of Git configuration settings to pass to the remote Git commands.

``sshPrivateKey``, ``sshHostKey``, ``sshKnownHosts``
   SSH authentication options supported by :bb:step:`Git`.

The Git server must permit ``git-upload-archive`` requests for the repository.
This is supported by Git's SSH and git protocols, but not by every Git hosting
service. The step also requires ``git`` and ``tar`` to be available on the
worker.
