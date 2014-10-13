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

* Both the P4 source step and P4 change source support ticket-based authentication.

Fixes
~~~~~

* Buildbot is now compatible with SQLAlchemy 0.8 and higher, using the newly-released SQLAlchemy-Migrate.

* The :bb:step:`HTTPStep` step's requeset parameters are now renderable.

* Fixed content spoofing vulnerabilities (#2589)

* Fixed cross-site scripting in status_json (#2943)

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

For a more detailed description of the changes made in this version, see the
git log itself:

.. code-block:: bash

   git log v0.8.9..master

Older Versions
--------------

Release notes for older versions of Buildbot are available in the :bb:src:`master/docs/relnotes/` directory of the source tree.
Newer versions are also available here:

.. toctree::
    :maxdepth: 1

    0.8.9
    0.8.8
    0.8.7
    0.8.6
