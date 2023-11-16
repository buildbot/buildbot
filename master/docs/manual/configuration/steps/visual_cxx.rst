.. index:: Visual Studio, Visual C++
.. bb:step:: VC6
.. bb:step:: VC7
.. bb:step:: VC8
.. bb:step:: VC9
.. bb:step:: VC10
.. bb:step:: VC11
.. bb:step:: VC12
.. bb:step:: VC14
.. bb:step:: VC141
.. bb:step:: VS2003
.. bb:step:: VS2005
.. bb:step:: VS2008
.. bb:step:: VS2010
.. bb:step:: VS2012
.. bb:step:: VS2013
.. bb:step:: VS2015
.. bb:step:: VS2017
.. bb:step:: VS2019
.. bb:step:: VS2022
.. bb:step:: VCExpress9
.. bb:step:: MsBuild4
.. bb:step:: MsBuild12
.. bb:step:: MsBuild14
.. bb:step:: MsBuild141
.. bb:step:: MsBuild15
.. bb:step:: MsBuild16
.. bb:step:: MsBuild17

.. _Step-VisualCxx:

Visual C++
++++++++++

These steps are meant to handle compilation using Microsoft compilers.
VC++ 6-141 (aka Visual Studio 2003-2015 and VCExpress9) are supported via calling ``devenv``.
Msbuild as well as Windows Driver Kit 8 are supported via the ``MsBuild4``, ``MsBuild12``, ``MsBuild14`` and  ``MsBuild141`` steps.
These steps will take care of setting up a clean compilation environment, parsing the generated output in real time, and delivering as detailed as possible information about the compilation executed.

All of the classes are in :mod:`buildbot.steps.vstudio`.
The available classes are:

* ``VC6``
* ``VC7``
* ``VC8``
* ``VC9``
* ``VC10``
* ``VC11``
* ``VC12``
* ``VC14``
* ``VC141``
* ``VS2003``
* ``VS2005``
* ``VS2008``
* ``VS2010``
* ``VS2012``
* ``VS2013``
* ``VS2015``
* ``VS2017``
* ``VS2019``
* ``VS2022``
* ``VCExpress9``
* ``MsBuild4``
* ``MsBuild12``
* ``MsBuild14``
* ``MsBuild141``
* ``MsBuild15``
* ``MsBuild16``
* ``MsBuild17``

The available constructor arguments are

``mode``
    The mode default to ``rebuild``, which means that first all the remaining object files will be cleaned by the compiler.
    The alternate values are ``build``, where only the updated files will be recompiled, and ``clean``, where the current build files are removed and no compilation occurs.

``projectfile``
    This is a mandatory argument which specifies the project file to be used during the compilation.

``config``
    This argument defaults to ``release`` an gives to the compiler the configuration to use.

``installdir``
    This is the place where the compiler is installed.
    The default value is compiler specific and is the default place where the compiler is installed.

``useenv``
    This boolean parameter, defaulting to ``False`` instruct the compiler to use its own settings or the one defined through the environment variables :envvar:`PATH`, :envvar:`INCLUDE`, and :envvar:`LIB`.
    If any of the ``INCLUDE`` or  ``LIB`` parameter is defined, this parameter automatically switches to ``True``.

``PATH``
    This is a list of path to be added to the :envvar:`PATH` environment variable.
    The default value is the one defined in the compiler options.

``INCLUDE``
    This is a list of path where the compiler will first look for include files.
    Then comes the default paths defined in the compiler options.

``LIB``
    This is a list of path where the compiler will first look for libraries.
    Then comes the default path defined in the compiler options.

``arch``
    That one is only available with the class VS2005 (VC8).
    It gives the target architecture of the built artifact.
    It defaults to ``x86`` and does not apply to ``MsBuild4`` or ``MsBuild12``.
    Please see ``platform`` below.

``project``
    This gives the specific project to build from within a workspace.
    It defaults to building all projects.
    This is useful for building cmake generate projects.

``platform``
    This is a mandatory argument for ``MsBuild4`` and ``MsBuild12`` specifying the target platform such as 'Win32', 'x64' or 'Vista Debug'.
    The last one is an example of driver targets that appear once Windows Driver Kit 8 is installed.
    
``defines``
    That one is only available with the MsBuild family of classes.
    It allows to define pre-processor constants used by the compiler.

Here is an example on how to drive compilation with Visual Studio 2013:

.. code-block:: python

    from buildbot.plugins import steps

    f.addStep(
        steps.VS2013(projectfile="project.sln", config="release",
            arch="x64", mode="build",
               INCLUDE=[r'C:\3rd-party\libmagic\include'],
               LIB=[r'C:\3rd-party\libmagic\lib-x64']))

Here is a similar example using "MsBuild12":

.. code-block:: python

    from buildbot.plugins import steps

    # Build one project in Release mode for Win32
    f.addStep(
        steps.MsBuild12(projectfile="trunk.sln", config="Release", platform="Win32",
                workdir="trunk",
                project="tools\\protoc"))

    # Build the entire solution in Debug mode for x64
    f.addStep(
        steps.MsBuild12(projectfile="trunk.sln", config='Debug', platform='x64',
                workdir="trunk"))
