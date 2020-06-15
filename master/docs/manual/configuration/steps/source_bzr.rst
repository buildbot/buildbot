.. bb:step:: Bzr

.. _Step-Bzr:

Bzr
+++

.. py:class:: buildbot.steps.source.bzr.Bzr

`bzr <http://bazaar.canonical.com/en/>`_ is a descendant of Arch/Baz, and is frequently referred to as simply `Bazaar`.
The repository-vs-workspace model is similar to Darcs, but it uses a strictly linear sequence of revisions (one history per branch) like Arch.
Branches are put in subdirectories.
This makes it look very much like Mercurial.

.. code-block:: python

    from buildbot.plugins import steps

    factory.addStep(steps.Bzr(mode='incremental',
                              repourl='lp:~knielsen/maria/tmp-buildbot-test'))

The step takes the following arguments:

``repourl``
    (required unless ``baseURL`` is provided): the URL at which the Bzr source repository is available.

``baseURL``
    (required unless ``repourl`` is provided): the base repository URL, to which a branch name will be appended.
    It should probably end in a slash.

``defaultBranch``
    (allowed if and only if ``baseURL`` is provided): this specifies the name of the branch to use when a Build does not provide one of its own.
    This will be appended to ``baseURL`` to create the string that will be passed to the ``bzr checkout`` command.
    If ``alwaysUseLatest`` is ``True`` then the branch and revision information that comes with the Build is ignored and branch specified in this parameter is used.

``mode``
``method``

    No method is needed for incremental mode.
    For full mode, ``method`` can take the values shown below.
    If no value is given, it defaults to ``fresh``.

    ``clobber``
        This specifies to remove the ``workdir`` and make a full checkout.

    ``fresh``
        This method first runs ``bzr clean-tree`` to remove all the unversioned files then ``update`` the repo.
        This remove all unversioned files including those in .bzrignore.

    ``clean``
        This is same as fresh except that it doesn't remove the files mentioned in :file:`.bzrginore` i.e, by running ``bzr clean-tree --ignore``.

    ``copy``
        A local bzr repository is maintained and the repo is copied to ``build`` directory for each build.
        Before each build the local bzr repo is updated then copied to ``build`` for next steps.

