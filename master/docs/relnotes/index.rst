Release Notes for Buildbot |version|
====================================

..
    Any change that adds a feature or fixes a bug should have an entry here.
    Most simply need an additional bulleted list item, but more significant
    changes can be given a subsection of their own.

The following are the release notes for Buildbot |version|.

Master
------

Features
~~~~~~~~

* GitHub change hook now supports application/json format.

* Buildbot is now compatible with Gerrit v2.6 and higher.

  To make this happen, the return result of ``reviewCB`` and ``summaryCB`` callback has changed from

  .. code-block:: python

     (message, verified, review)

  to

  .. code-block:: python

     {'message': message,
      'labels': {'label-name': value,
                ...
                }
     }

  The implications are:

  * there are some differences in behaviour: only those labels that were provided will be updated
  * Gerrit server must be able to provide a version, if it can't the :bb:status:`GerritStatusPush` will not work

  .. note::

     If you have an old style ``reviewCB`` and/or ``summaryCB`` implemented, these will still work, however there could be more labels updated than anticipated.

  More detailed information is available in :bb:status:`GerritStatusPush` section.

* Buildbot now supports plugins.
  They allow Buildbot to be extended by using components distributed independently from the main code.
  They also provide for a unified way to access all components.
  When previously the following construction was used::

      from buildbot.kind.other.bits import ComponentClass

      ... ComponentClass ...

  the following construction achieves the same result::

      from buildbot.plugins import kind

      ... kind.ComponentClass ...

  Kinds of components that are available this way are described in :doc:`../manual/plugins`.

  .. note::

     While the components can be still directly imported as ``buildbot.kind.other.bits``, this might not be the case after Buildbot v1.0 is released.

* :bb:chsrc:`GitPoller` now supports detecting new branches

Fixes
~~~~~

* GitHub change hook now correctly responds to ping events.
* ``buildbot.steps.http`` steps now correctly have ``url`` parameter renderable

Deprecations, Removals, and Non-Compatible Changes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Changes for Developers
~~~~~~~~~~~~~~~~~~~~~~

Slave
-----

Features
~~~~~~~~

Fixes
~~~~~

Deprecations, Removals, and Non-Compatible Changes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Details
-------

For a more detailed description of the changes made in this version, see the git log itself:

.. code-block:: bash

   git log v0.8.10..eight

Older Versions
--------------

Release notes for older versions of Buildbot are available in the :bb:src:`master/docs/relnotes/` directory of the source tree.
Newer versions are also available here:

.. toctree::
    :maxdepth: 1

    0.8.10
    0.8.9
    0.8.8
    0.8.7
    0.8.6
