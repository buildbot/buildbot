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

Version Control Comparison
--------------------------

Buildbot supports a number of version control systems, and they don't all agree
on their terms.  This table should help to disambiguate them.

=========== =========== =========== ===================
Name        Change      Revision    Branches
=========== =========== =========== ===================
CVS         patch [1]   timestamp   unnamed
Subversion  revision    integer     directories
Git         commit      sha1 hash   named refs
Mercurial   changeset   sha1 hash   different repos
                                    or (permanently)
                                    named commits
Darcs       ?           none [2]    different repos
Bazaar      ?           ?           ?
Perforce    ?           ?           ?
BitKeeper   changeset   ?           different repos
=========== =========== =========== ===================

* [1] note that CVS only tracks patches to individual files.  Buildbot tries to
  recognize coordinated changes to multiple files by correlating change times.

* [2] Darcs does not have a concise way of representing a particular revision
  of the source.
