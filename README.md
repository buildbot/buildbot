What?  This doesn't look like a README!

Right, this is the TODO list for Buildbot-0.9.0.  We'll delete this once it's empty.  Pitch in!

# Infrastructure #

* Optimize the type verification system by dynamically creating verifier functions once.

# Documentation #

* Rename ``masters/docs/developer/database.rst`` to ``db.rst`` for consistency.
* Put update methods in the appropriate resource-type files, rather than in ``data.rst``
* Move data API how-to guides

# Data API #

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

## Remaining Resource Types ##

The outstanding resource types are:

* scheduler (underlying DB API complete)
* builder
* sourcestamp
* buildrequest
* build
* step
* logfile
* buildslave

### Schedulers ###

There is no scheduler resource type yet, although schedulers are in place in the database API so that other tables can refer to a scheduler ID.
Support needs to be added for schedulers on a particular master to "claim" the name for themselves, deactivate themselves if already running on another master, and periodically poll for the opportunity to pick up the role.
This gives us automatic failover for schedulers in a multi-master configuration, and also means that all masters can run with identical configurations, which may make configuration management easier.

When a master becomes inactive (either on its own, or having failed its heartbeat check), its schedulers should be marked inactive by the data API and suitable messages sent.

It should be possible to list the master on which a scheduler is running at e.g., `/scheduler/:schedulerid/master`

### Builders ###

* Add identifiers for builders (url-component safe strings), and allow use of those in place of integer IDs in data API paths.

### Buildrequests ###

Buildrequests include a `builderid` field which will need to be determined from the builders table.
It should probably be an error to schedule a build on a builder that does not exist, as that build will not be executed.
It's OK to schedule a build on a builder that's not implemented by a running master, though.

## Other Resource-Type Related Tasks ##

* ``addBuildset`` currently sends messages about buildrequests directly.
  It should, instead, coordinate with the buildrequests resource type to do so.
* Add support for uids to the change resource type

## Misc Data API Work ##

* Paging, filtering, and so on of data API results.
* Parsing of endpoint options is currently left to the endpoint, which will lead to inconsistencies.
  Add and document some helper methods to ``base.Endpoint`` for parsing e.g., boolean options (supporting on/off, 0/1, true/false, etc.)
* If several rtypes have `_db2data` functions or similar (so far masters and changes both do), then make that an idiom and document it.

# Web #

## Infrastructure ##

* Remaining parts of buildbot-www package (after which much of this section is complete):

  * Replace `update_js` with use of entry points to find buildbot-www package
  * support multiple entry points for easy user extensions
  * ensure tests run either from `built/` or `src/` of buildbot-www
  * verify licensing on all bundled projects
  * documentation

* Build the router.js config dynamically on the master, either at startup or in upgrade-master.

  * For now, this is done using `extra_js` parameter of the www config

* Dynamically download or proxy external resources, so they're not included in the Buildbot source or the tarball.
  This download can occur either at startup, or in upgrade-master.
  => Done with buildbot updatejs, which is also part of upgarde-master/create-master

* Minify and concatenate JS source at startup or upgrade-master.
  http://opensource.perlig.de/rjsmin/ may help here; it has a compatible license and is a single file.

  * dojo is supporting this with its build system. For now this build sytem is
    very powerful, and allow to select which modules are needed, and do several
    layers but it needs nodejs and java. There are work in order to remove the
    java needs that will probably land before nine in dojo's mainline.
    http://bugs.dojotoolkit.org/ticket/14684

* Add cache headers to the HTTP server, based on information encoded in the resource types regarding immutability and speed of change.
* haml-js is used as a templating system. haml-js has been selected over other templating system for its big simplicity + power combination.
  2 Problems with haml-js run in browser:

   * it is not compatible with IE8, because it is using ECMAScript 4 features
   * it is difficult to integrate with dojo build system, and embeded the templates into the concatenated js file.

  To workaround this problem, the translation from haml template to js program is done at server side, at the updatejs time. This leverage a dependancy
  on node, and installing hamlcc via npm. long term solution is probably to translate haml-js in python, or reuse a haml python implementation to produce js code
  instead of python

## Javascript ##

* Standardize on interCaps spellings for identifiers (method and variable names).

## Javascript Testing ##

Testing javascript and json api interaction is tricky. Few design principles:
* Stubbing the data api in JS is considered wrong path, as we'll have to always make sure consistency between the stub and real implementation
* Run JS inside trial environment is difficult. txghost.py method has been experimented, and has several drawbacks.
  - ghost is based on webkit which in turn is based on qt. The qtreactor had licence issue and is not well supported in twisted. So there is a
    hack in txghost trying to run the qt event loop at the same time as the twisted event loop.
  - better solution would be to run ghost in its own process, and have minimal RPC to control it. RPC between twisted and qt looks complicated.
  - installing pyqt/webkit inside virtualenv is tricky. You need to manually copy some of the .so libraries inside the sandbox
* better option has been discussed:
  - let the JS test suite be entirely JS driven, and not python trial driven + JS assertion, like originally though
  - JS tests can control data api, and trigger fake events via a special testing data api.
  - JS developer can run its test without trial knowledge. Only points the browser to doh's runner.html page, and run the tests:
    e.g.: http://nine.buildbot.net/nine/static/js/lib/tests/runner.html#all
  - Need a js test mode that has to be enabled in master.cfg, in order to prevent prod's db to be corrupted by tests if malicious people launch them
  - Test mode will add some data api to inject pre-crafted events in the data flow.

## Vague Ideas ##

These are just "things that need doing", where we don't have much idea *how* yet:

* i18n/l10n support so contributors can easily translate the web UI
  => dojo has support for i18n/l10n and accessibility
* Use TastyPie as a model for a generic REST API library
  => We decided to use data as a basis for REST API, we just need a translation layer for data <-> json REST, implemented in rest.py

* Need to download bootstrap from upstream instead of having a hardcopy in our source code.

# Database Updates #

We're deferring any changes to the database schema for as long as possible, because they are difficult to maintain on a branch.
So, they're listed here.

## Schema Changes ##

Don't include the schema changes needed to implement the status stuff here; those will come when we implement the status stuff.

* Remove ``is_dir`` from the changes table (and ignore/remove it everywhere else)
* Add a ``changesources`` table, similar to schedulers

For each of the config-objects tables (masters, builders, schedulesr, changesources):

 * New table
 * Migration script + tests
 * DB API module + docs, type verifier, and interface tests
 * Fake implementation that passes interface tests 
 * Add TODO for data API implementation

## DB API Changes ##

* Switch to use epoch time throughout the DB API.
* Use None/NULL, not -1, as the "no results yet" sentinel value in buildsets and buildrequests
* Make `completeBuildSet` return true if the database claims to have updated the row, and use that to narrow the race condition in `maybeBuildsetComplete`
* Use sa.Text instead of sa.String(LEN), so we have unlimited-length strings.
  Where indexes -- especially unique indexes -- are required on these columns, add sha1 hash columns and index those.
  Among other advantages, this will allow MySQL databases to use the vastly superior InnoDB table type.

## Documentation ##

* Document Buildbot's behavior for a DBA: isolation assumptions, dependencies on autogenerated IDs, read-after-write expectations, buildrequest claiming, buildset completion detection

## Miscellaneous ##

* Factor the mutiple select-or-insert methods (e.g., for masters) into a common utility method.
* Look carefully at race conditions around masters being marked inactive

# Later #

This section can hold tasks that don't need to be done by 0.9.0, but shouldn't be forgotten, and might be implemented sooner if convenient.

## Infrastructure ##

* Use some fancy algorithms to delay message transmission until the data is known-good in the database, for cases where the underlying database is asynchronously replicated.

## Documentation ##

* Document how to write a scheduler: the ``addBuildsetForXxx`` methods, as well as the proper procedure for listening for changes.
