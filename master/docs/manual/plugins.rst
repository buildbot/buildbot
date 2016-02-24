.. _Plugins:

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

``worker``
    workers, described in :doc:`cfg-workers`

``changes``
    change source, described in :doc:`cfg-changesources`

``schedulers``
    schedulers, described in :doc:`cfg-schedulers`

``steps``
    build steps, described in :doc:`cfg-buildsteps`

``reporters``
    reporters (or reporter targets), described in :doc:`cfg-reporters`

``util``
    utility classes.
    For example, :doc:`BuilderConfig <cfg-builders>`, :doc:`cfg-buildfactories`, :ref:`ChangeFilter <Change-Filters>` and :doc:`Locks <cfg-interlocks>` are accessible through ``util``.

Web interface plugins are not used directly: as described in :doc:`web server configuration <cfg-www>` section, they are listed in the corresponding section of the web server configuration dictionary.

.. note::

    If you are not very familiar with Python and you need to use different kinds of components, start your ``master.cfg`` file with::

        from buildbot.plugins import *

    As a result, all listed above components will be available for use.
    This is what sample ``master.cfg`` file uses.

Finding Plugins
===============

Buildbot maintains a list of plugins at http://trac.buildbot.net/wiki/Plugins.

Developing Plugins
==================

:ref:`Plugin-Module` contains all necesary information for you to develop new plugins.
Please edit http://trac.buildbot.net/wiki/Plugins to add a link to your plugin!

Plugins of note
===============

Plugins were introduced in Buildbot-0.8.11, so as of this writing, only components that are bundled with Buildbot are available as plugins.

If you have an idea/need about extending Buildbot, head to :doc:`../developer/plugins-publish`, create your own plugins and let the world now how Buildbot can be made even more useful.
