
.. bb:step:: Darcs

.. _Step-Darcs:

Darcs
+++++

.. py:class:: buildbot.steps.source.darcs.Darcs

The :bb:step:`Darcs` build step performs a `Darcs <http://darcs.net/>`_ checkout or update.

.. code-block:: python

    from buildbot.plugins import steps

    factory.addStep(steps.Darcs(repourl='http://path/to/repo',
                                mode='full', method='clobber', retry=(10, 1)))

Darcs step takes the following arguments:

``repourl``
    (required): The URL at which the Darcs source repository is available.

``mode``

    (optional): defaults to ``'incremental'``.
    Specifies whether to clean the build tree or not.

    ``incremental``
      The source is update, but any built files are left untouched.

    ``full``
      The build tree is clean of any built files.
      The exact method for doing this is controlled by the ``method`` argument.

``method``
   (optional): defaults to ``copy`` when mode is ``full``.
   Darcs' incremental mode does not require a method.
   The full mode has two methods defined:

   ``clobber``
      It removes the working directory for each build then makes full checkout.

   ``copy``
      This first checkout source into source directory then copy the ``source`` directory to ``build`` directory then performs the build operation in the copied directory.
      This way we make fresh builds with very less bandwidth to download source.
      The behavior of source checkout follows exactly same as incremental.
      It performs all the incremental checkout behavior in ``source`` directory.
