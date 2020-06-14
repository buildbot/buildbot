.. bb:step:: CMake

.. _Step-CMake:

CMake
+++++

.. py:class:: buildbot.steps.cmake.CMake

This is intended to handle the :command:`cmake` step for projects that use `CMake-based build systems <http://cmake.org>`_.

.. note::

   Links below point to the latest CMake documentation.
   Make sure that you check the documentation for the CMake you use.

In addition to the parameters :bb:step:`ShellCommand` supports, this step accepts the following parameters:

``path``
    Either a path to a source directory to (re-)generate a build system for it in the current working directory.
    Or an existing build directory to re-generate its build system.

``generator``
    A build system generator.
    See `cmake-generators(7) <https://cmake.org/cmake/help/latest/manual/cmake-generators.7.html>`_ for available options.

``definitions``
    A dictionary that contains parameters that will be converted to ``-D{name}={value}`` when passed to CMake.
    A renderable which renders to a dictionary can also be provided, see :ref:`Properties`.
    Refer to `cmake(1) <https://cmake.org/cmake/help/latest/manual/cmake.1.html>`_ for more information.

``options``
    A list or a tuple that contains options that will be passed to CMake as is.
    A renderable which renders to a tuple or list can also be provided, see :ref:`Properties`.
    Refer to `cmake(1) <https://cmake.org/cmake/help/latest/manual/cmake.1.html>`_ for more information.

``cmake``
    Path to the CMake binary.
    Default is :command:`cmake`

.. code-block:: python

    from buildbot.plugins import steps

    ...

    factory.addStep(
        steps.CMake(
            generator='Ninja',
            definitions={
                'CMAKE_BUILD_TYPE': Property('BUILD_TYPE')
            },
            options=[
                '-Wno-dev'
            ]
        )
    )

    ...
