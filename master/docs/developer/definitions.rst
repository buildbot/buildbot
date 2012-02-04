Definitions
===========

Buildbot uses some terms and concepts that have specific meanings.

Repository
----------

The ``respository`` attribute attached to things like changes and source stamps
unambiguously describes the repository in which the particular revision can be
found.  No other context should be required.  For most version-control systems,
this takes the form of a URL.

Project
-------

The ``project`` attribute of a change or source stamp describes the project to
which it corresponds, as a short human-readable string.  This is useful in
cases where multiple independent projects are built on the same buildmaster.
In such cases, it can be used to limit status displays to only one project.
