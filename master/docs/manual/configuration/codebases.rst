.. bb:cfg:: codebases

.. _Codebase-Configuration:

Codebases
---------

.. contents::
    :depth: 1
    :local:

The :bb:cfg:`codebases` configuration key is a list of objects holding the configuration of Codebases.
For more information on the Codebase function in Buildbot, see :ref:`the Concepts chapter <Concepts-Project>`.

``Codebase`` takes the following keyword arguments:

``name``
    The name of the Codebase.

    The name must be unique across all codebases that are part of the project.

    If ``name`` is changed, then a new codebase is created with respect to historical data stored
    by Buildbot.

``project``
    The name of the project that codebase is part of.

The following arguments are optional:

``slug``
    (string, optional)
    A short string that identifies the codebase.

    Among other things, it may be used to refer to the codebase in the URLs of the Buildbot web UI.

    By default ``slug`` is equal to ``name``.

Example
~~~~~~~

The following is a demonstration of defining several Projects in the Buildbot configuration

.. code-block:: python

    from buildbot.plugins import util
    c['projects'] = [
        util.Project(name="example",
                     description="An application to build example widgets"),
        util.Project(name="example-utils",
                     description="Utilities for the example project"),
    ]
    c['codebases'] = [
        util.Codebase(name="main", project='example'),
        util.Codebase(name="main", project='example-utils'),
    ]
