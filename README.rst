What?  This doesn't look like a README!

Right, this is the TODO list for Buildbot-0.9.0.  We'll delete this once it's empty.  Pitch in!

Infrastructure
==============

 * Parsing of endpoint options is currently left to the endpoint, which will lead to inconsistencies.
   Add and document some helper methods to ``base.Endpoint`` for parsing e.g., boolean options (supporting on/off, 0/1, true/false, etc.)
 * Optimize the type verification system by dynamically creating verifier functions once.

Documentation
+++++++++++++

 * Rename ``masters/docs/developer/database.rst`` to ``db.rst`` for consistency.
 * Put update methods in the appropriate resource-type files, rather than in ``data.rst``
 * Move data API how-to guides

Resource Types
==============

For each resource type, we'll need the following (based on "Adding Resource Types" in ``master/docs/developer/data.rst``).  use this list as a template in the list of types below when you begin a new type.

    * A resource-type module and class, with unit tests
    * Docs for that resource type
    * Type validators for the resource type
    * New endpoints, with unit tests
    * Docs for the endpoints
    * Appropriate update methods, with unit tests
    * Docs for those update methods
    * Integrate with Buildbot: process classes should use the data API and not the DB or MQ APIs.

It's safe to leave tasks that have significant prerequisites - particularly the last point - commented as "TODO" in the source, with corresponding items added here.

Remaining Types
---------------

The outstanding resource types are:

 * scheduler
 * builder
 * buildrequest
 * build
 * step
 * logfile
 * buildslave

Other Tasks
-----------

 * Improve usage of ``assertBuildset`` in scheduler tests.
   Right now, many of them fail to assert some details of what they've inserted.
   This will need to wait until at least the buildrequests resource type is defined.
 * ``addBuildset`` currently sends messages about buildrequests directly.
   It should, instead, coordinate with the buildrequests resource type to do so.
 * Add support for uids to the change resource type

Web
===

Infrastructure
--------------

 * Build the router.js config dynamically on the master, either at startup or in upgrade-master.
 * Dynamically download or proxy external resources, so they're not included in the Buildbot source or the tarball.
   This download can occur either at startup, or in upgrade-master.
 * Minify and concatenate JS source at startup or upgrade-master.
   http://opensource.perlig.de/rjsmin/ may help here; it has a compatible license and is a single file.
 * Add cache headers to the HTTP server, based on information encoded in the resource types regarding immutability and speed of change.

Javascript
----------

 * Standardize on interCaps spellings for identifiers.

Vague Topics
------------

These are just "things that need doing", where we don't have much idea *how* yet:

 * i18n/l10n support so contributors can easily translate the web UI
 * Use TastyPie as a model for a generic REST API library

Database Updates
================

We're deferring any changes to the database schema for as long as possible, because they are difficult to maintain on a branch.
So, they're listed here.

Schema Changes
++++++++++++++

 * Remove ``is_dir`` from the changes table (and ignore/remove it everywhere else)
 * Add a ``masters`` table
 * Add a ``builders`` table

API Changes
+++++++++++

 * Switch to use epoch time throughout the DB API.
 * Use None/NULL, not -1, as the "no results yet" sentinel value in buildsets and buildrequests

Later
=====

This section can hold tasks that don't need to be done by 0.9.0, but shouldn't be forgotten, and might be implemented sooner if convenient.

Infrastructure
--------------

* Use some fancy algorithms to delay message transmission until the data is known-good in the database, for cases where the underlying database is asynchronously replicated.

Documentation
-------------

 * Document how to write a scheduler: the ``addBuildsetForXxx`` methods, as well as the proper procedure for listening for changes.
