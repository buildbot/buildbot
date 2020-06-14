.. bb:step:: Monotone

.. _Step-Monotone:

Monotone
++++++++

.. py:class:: buildbot.steps.source.mtn.Monotone

The :bb:step:`Monotone` build step performs a `Monotone <http://www.monotone.ca/>`_ checkout or update.

.. code-block:: python

    from buildbot.plugins import steps

    factory.addStep(steps.Monotone(repourl='http://path/to/repo',
                                   mode='full', method='clobber',
                                   branch='some.branch.name', retry=(10, 1)))


Monotone step takes the following arguments:

``repourl``
    the URL at which the Monotone source repository is available.

``branch``
    this specifies the name of the branch to use when a Build does not provide one of its own.
    If ``alwaysUseLatest`` is ``True`` then the branch and revision information that comes with the Build is ignored and branch specified in this parameter is used.

``progress``
    this is a boolean that has a pull from the repository use ``--ticker=dot`` instead of the default ``--ticker=none``.

``mode``

  (optional): defaults to ``'incremental'``.
  Specifies whether to clean the build tree or not.
  In any case, the worker first pulls from the given remote repository
  to synchronize (or possibly initialize) its local database. The mode
  and method only affect how the build tree is checked-out or updated
  from the local database.

    ``incremental``
      The source is update, but any built files are left untouched.

    ``full``
      The build tree is clean of any built files.
      The exact method for doing this is controlled by the ``method`` argument.
      Even in this mode, the revisions already pulled remain in the database
      and a fresh pull is rarely needed.

``method``

   (optional): defaults to ``copy`` when mode is ``full``.
   Monotone's incremental mode does not require a method.
   The full mode has four methods defined:

   ``clobber``
      It removes the build directory entirely then makes fresh checkout from
      the database.

   ``clean``
      This remove all other files except those tracked and ignored by Monotone.
      It will remove all the files that appear in :command:`mtn ls unknown`.
      Then it will pull from remote and update the working directory.

   ``fresh``
      This remove all other files except those tracked by Monotone.
      It will remove all the files that appear in :command:`mtn ls ignored` and :command:`mtn ls unknows`.
      Then pull and update similar to ``clean``

   ``copy``
      This first checkout source into source directory then copy the ``source`` directory to ``build`` directory then performs the build operation in the copied directory.
      This way we make fresh builds with very less bandwidth to download source.
      The behavior of source checkout follows exactly same as incremental.
      It performs all the incremental checkout behavior in ``source`` directory.
