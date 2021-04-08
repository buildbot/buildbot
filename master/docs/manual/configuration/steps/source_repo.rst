.. index:: double: Gerrit integration; Repo Build Step

.. bb:step:: Repo

.. _Step-Repo:

Repo
++++

.. py:class:: buildbot.steps.source.repo.Repo

The :bb:step:`Repo` build step performs a `Repo <http://lwn.net/Articles/304488/>`_ init and sync.

The Repo step takes the following arguments:

``manifestURL``
    (required): the URL at which the Repo's manifests source repository is available.

``manifestBranch``
    (optional, defaults to ``master``): the manifest repository branch on which repo will take its manifest.
    Corresponds to the ``-b`` argument to the :command:`repo init` command.

``manifestFile``
    (optional, defaults to ``default.xml``): the manifest filename.
    Corresponds to the ``-m`` argument to the :command:`repo init` command.

``tarball``
    (optional, defaults to ``None``): the repo tarball used for fast bootstrap.
    If not present the tarball will be created automatically after first sync.
    It is a copy of the ``.repo`` directory which contains all the Git objects.
    This feature helps to minimize network usage on very big projects with lots of workers.

    The suffix of the tarball determines if the tarball is compressed and which compressor is chosen.
    Supported suffixes are ``bz2``, ``gz``, ``lzma``, ``lzop``, and ``pigz``.

``jobs``
    (optional, defaults to ``None``): Number of projects to fetch simultaneously while syncing.
    Passed to repo sync subcommand with "-j".

``syncAllBranches``
    (optional, defaults to ``False``): renderable boolean to control whether ``repo`` syncs all branches.
    I.e. ``repo sync -c``

``depth``
    (optional, defaults to 0): Depth argument passed to repo init.
    Specifies the amount of git history to store.
    A depth of 1 is useful for shallow clones.
    This can save considerable disk space on very large projects.

``submodules``
    (optional, defaults to ``False``): sync any submodules associated with the manifest repo.
    Corresponds to the ``--submodules`` argument to the :command:`repo init` command.

``updateTarballAge``
    (optional, defaults to "one week"): renderable to control the policy of updating of the tarball given properties.
    Returns: max age of tarball in seconds, or ``None``, if we want to skip tarball update.
    The default value should be good trade off on size of the tarball, and update frequency compared to cost of tarball creation

``repoDownloads``
    (optional, defaults to None): list of ``repo download`` commands to perform at the end of the Repo step each string in the list will be prefixed ``repo download``, and run as is.
    This means you can include parameter in the string.
    For example:

    * ``["-c project 1234/4"]`` will cherry-pick patchset 4 of patch 1234 in project ``project``
    * ``["-f project 1234/4"]`` will enforce fast-forward on patchset 4 of patch 1234 in project ``project``

.. py:class:: buildbot.steps.source.repo.RepoDownloadsFromProperties

``util.repo.DownloadsFromProperties`` can be used as a renderable of the ``repoDownload`` parameter it will look in passed properties for string with following possible format:

*  ``repo download project change_number/patchset_number``
*  ``project change_number/patchset_number``
*  ``project/change_number/patchset_number``

All of these properties will be translated into a :command:`repo download`.
This feature allows integrators to build with several pending interdependent changes, which at the moment cannot be described properly in Gerrit, and can only be described by humans.

.. py:class:: buildbot.steps.source.repo.RepoDownloadsFromChangeSource

``util.repo.DownloadsFromChangeSource`` can be used as a renderable of the ``repoDownload`` parameter

This rendereable integrates with :bb:chsrc:`GerritChangeSource`, and will automatically use the :command:`repo download` command of repo to download the additional changes introduced by a pending changeset.

.. note::

   You can use the two above Rendereable in conjunction by using the class ``buildbot.process.properties.FlattenList``

For example:

.. code-block:: python

    from buildbot.plugins import steps, util

    factory.addStep(steps.Repo(manifestURL='git://gerrit.example.org/manifest.git',
                               repoDownloads=util.FlattenList([
                                    util.RepoDownloadsFromChangeSource(),
                                    util.RepoDownloadsFromProperties("repo_downloads")
                               ])))
