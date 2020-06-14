.. bb:step:: Mercurial

.. _Step-Mercurial:

Mercurial
+++++++++

.. py:class:: buildbot.steps.source.mercurial.Mercurial

The :bb:step:`Mercurial` build step performs a `Mercurial <https://www.mercurial-scm.org/>`_ (aka ``hg``) checkout or update.

Branches are available in two modes: ``dirname``, where the name of the branch is a suffix of the name of the repository, or ``inrepo``, which uses Hg's named-branches support.
Make sure this setting matches your changehook, if you have that installed.

.. code-block:: python

    from buildbot.plugins import steps

    factory.addStep(steps.Mercurial(repourl='path/to/repo', mode='full',
                                    method='fresh', branchType='inrepo'))

The Mercurial step takes the following arguments:

``repourl``
   where the Mercurial source repository is available.

``defaultBranch``
   this specifies the name of the branch to use when a Build does not provide one of its own.
   This will be appended to ``repourl`` to create the string that will be passed to the ``hg clone`` command.
   If ``alwaysUseLatest`` is ``True`` then the branch and revision information that comes with the Build is ignored and branch specified in this parameter is used.

``branchType``
   either 'dirname' (default) or 'inrepo' depending on whether the branch name should be appended to the ``repourl`` or the branch is a Mercurial named branch and can be found within the ``repourl``.

``clobberOnBranchChange``
   boolean, defaults to ``True``.
   If set and using inrepos branches, clobber the tree at each branch change.
   Otherwise, just update to the branch.

``mode``
``method``

   Mercurial's incremental mode does not require a method.
   The full mode has three methods defined:


   ``clobber``
      It removes the build directory entirely then makes full clone from repo.
      This can be slow as it need to clone whole repository

   ``fresh``
      This remove all other files except those tracked by VCS.
      First it does :command:`hg purge --all` then pull/update

   ``clean``
      All the files which are tracked by Mercurial and listed ignore files are not deleted.
      Remaining all other files will be deleted before pull/update.
      This is equivalent to :command:`hg purge` then pull/update.
