.. bb:cfg:: projects

.. _Project-Configuration:

Projects
--------

.. contents::
    :depth: 1
    :local:

The :bb:cfg:`projects` configuration key is a list of objects holding the configuration of the Projects.
For more information on the Project function in Buildbot, see :ref:`the Concepts chapter <Concepts-Project>`.

``Project`` takes the following keyword arguments:

``name``
    The name of the Project.
    Builders are associated to the Project using this string as their ``project`` parameter.

The following arguments are optional:

``slug``
    (string, optional)
    A short string that is used to refer to the project in the URLs of the Buildbot web UI.

``description``
    (string, optional)
    A description of the project that appears in the Buildbot web UI.

``description_format``
    (string, optional)

    The format of the ``description`` parameter.
    By default, it is ``None`` and corresponds to plain text format.
    Allowed values: ``None``, ``markdown``.

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
