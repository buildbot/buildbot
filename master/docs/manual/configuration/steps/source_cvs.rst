.. bb:step:: CVS

.. _Step-CVS:

CVS
+++

.. py:class:: buildbot.steps.source.cvs.CVS

The :bb:step:`CVS` build step performs a `CVS <http://www.nongnu.org/cvs/>`_ checkout or update.

.. code-block:: python

    from buildbot.plugins import steps

    factory.addStep(steps.CVS(mode='incremental',
                    cvsroot=':pserver:me@cvs.example.net:/cvsroot/myproj',
                    cvsmodule='buildbot'))

This step takes the following arguments:

``cvsroot``
    (required): specify the CVSROOT value, which points to a CVS repository, probably on a remote machine.
    For example, if Buildbot was hosted in CVS then the CVSROOT value you would use to get a copy of the Buildbot source code might be ``:pserver:anonymous@cvs.example.net:/cvsroot/buildbot``.

``cvsmodule``
    (required): specify the cvs ``module``, which is generally a subdirectory of the :file:`CVSROOT`.
    The cvsmodule for the Buildbot source code is ``buildbot``.

``branch``
    a string which will be used in a ``-r`` argument.
    This is most useful for specifying a branch to work on.
    Defaults to ``HEAD``.
    If ``alwaysUseLatest`` is ``True`` then the branch and revision information that comes with the Build is ignored and branch specified in this parameter is used.

``global_options``
    a list of flags to be put before the argument ``checkout`` in the CVS command.

``extra_options``
    a list of flags to be put after the ``checkout`` in the CVS command.

``mode``
``method``

    No method is needed for incremental mode.
    For full mode, ``method`` can take the values shown below.
    If no value is given, it defaults to ``fresh``.

    ``clobber``
        This specifies to remove the ``workdir`` and make a full checkout.

    ``fresh``
        This method first runs ``cvsdisard`` in the build directory, then updates it.
        This requires ``cvsdiscard`` which is a part of the cvsutil package.

    ``clean``
        This method is the same as ``method='fresh'``, but it runs ``cvsdiscard --ignore`` instead of ``cvsdiscard``.

    ``copy``
        This maintains a ``source`` directory for source, which it updates copies to the build directory.
        This allows Buildbot to start with a fresh directory, without downloading the entire repository on every build.

``login``
    Password to use while performing login to the remote CVS server.
    Default is ``None`` meaning that no login needs to be performed.
