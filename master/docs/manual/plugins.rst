=================================
Plugin Infrastructure in Buildbot
=================================

.. versionadded:: 0.8.11

Plugin infrastructure in Buildbot allows easy use of components that are not part of the core.
It also allows unified access to components that are included in the core.

The following snippet

.. code-block:: python

    from buildbot.plugins import kind

    ... kind.ComponentClass ...

allows to use a component of kind ``kind``.
Available ``kind``\s are:

``buildslave``
    build slaves, described in :doc:`cfg-buildslaves`

``changes``
    change source, described in :doc:`cfg-changesources`

``schedulers``
    schedulers, described in :doc:`cfg-schedulers`

``steps``
    build steps, described in :doc:`cfg-buildsteps`

``status``
    status targets, described in :doc:`cfg-statustargets`

``util``
    utility classes.  For example, :doc:`BuilderConfig <cfg-builders>`, :doc:`cfg-buildfactories`, :ref:`ChangeFilter <Change-Filters>` and :doc:`Locks <cfg-interlocks>` are accessible through ``util``.

.. note::

    If you are not very familiar with Python and you need to use different kinds of components, start your ``master.cfg`` file with::

        from buildbot.plugins import *

    As a result, all listed above components will be available for use.
    This is what sample ``master.cfg`` file uses.

Developing Plugins
==================

:ref:`Plugin-Module` contains all necesary information for you to develop new plugins.

Plugins of note
===============

Plugins were introduced in Buildbot-0.9.0, so as of this writing, only components that are bundled with Buildbot are available as plugins.

If you have an idea/need about extending Buildbot, head to :doc:`../developer/plugins-publish`, create your own plugins and let the world now how Buildbot can be made even more useful.
