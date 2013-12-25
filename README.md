What?  This doesn't look like a README!

Right, this is the TODO list for Buildbot-0.9.0.  We'll delete this once it's empty.  Pitch in!

# Overall Goals #

The 'nine' branch is a refactoring of Buildbot into a consistent, well-defined application composed of loosely coupled components.
The components are linked by a common database backend and a messaging system.
This allows components to be distributed across multiple build masters.
It also allows the rendering of complex web status views to be performed in the browser, rather than on the buildmasters.

The branch looks forward to committing to long-term API compatibility, but does not reach that goal.
The Buildbot-0.9.x series of releases will give the new APIs time to "settle in" before we commit to them.
Commitment will wait for Buildbot-1.0.0 (as per http://semver.org).
Once Buildbot reaches version 1.0.0, upgrades will become much easier for users.

To encourage contributions from a wider field of developers, the web application is designed to look like a normal AngularJS application.
Developers familiar with AngularJS, but not with Python, should be able to start hacking on the web application quickly.
The web application is "pluggable", so users who develop their own status displays can package those separately from Buildbot itself.

Other goals:
 * An approachable HTTP REST API, used by the web application but available for any other purpose.
 * A high degree of coverage by reliable, easily-modified tests.
 * "Interlocking" tests to guarantee compatibility.
   For example, the real and fake DB implementations must both pass the same suite of tests.
   Then no unseen difference between the fake and real implementations can mask errors that will occur in production.

## Compatibility ##

Upgrading Buildbot has always been difficult.
The upgrade to 0.9.0 will be difficult, too -- the requirements make that unavoidable.
However, we want to minimize the difficulty wherever possible, and be absolutely clear about any changes to documented behavior.
The release notes should give detailed upgrade instructions wherever the changes are not automatic.

## Requirements ##

For users, Buildbot's requirements will not change.

Buildbot-0.8.x requires:

 * Python (obviously)
 * Some DB (sqlite, etc. -- sqlite is built into Python)

Buildbot-0.9.x will require:

 * Python (obviously)
 * Some DB (sqlite, etc. -- sqlite is built into Python)

but it's a little more complicated:

 * If you want to do web *development*, or *build* the buildbot-www package, you'll need Node.
   It's an Angular app, and that's how such apps are developed.
   We've taken pains to not make either a requirement for users - you can simply 'pip install' buildbot-www and be on your way.
   This is the case even if you're hacking on the Python side of Buildbot.
 * For a single master, nothing else is required.
 * If you want multiple masters, you'll need a server-based DB (already the case in 0.8.x) and a messaging system of some sort.
   Messaging requirements will be similar to DB requirements: small installs can use something built-in that doesn't scale well.
   Larger installs can use external tools with better scaling behavior.

# Development Tasks #

## Progress ##

At this point, most of the configuration objects (masters, schedulers, builders, etc.) and everything that is in the DB in 0.8.x are ported to the Data API.
The status objects (builds, steps, logs, log chunks) are defined in the DB and Data APIs, but Buildbot does not yet insert data into the database tables while performing a build.
The next step is to insert this data, and then remove support for the existing status hierarchy.
Each of the existing status listeners - irc, WebStatus, MailNotifier, etc. - will need to be rewritten based on the Data API.

## Process ##

The "process" part of Buildbot is the part that coordinates all of the other parts - the master, botmaster, etc.  Remaining work in the Buildbot process code includes:

* Request collapsing - see https://plus.google.com/105883044168332773236/posts/TG8DHus4L4D
  Builds for merged requests currently only refer to one of the merged requests.
* In the Trigger step, add links from the triggering step to the triggered builds
* Create builds, steps, logs, and log chunks during execution of a build.
* Simplify LogLineObserver - this class is designed to handle arbitrary chunks of log data, but now chunks always end on a line boundary.
  It can be substantially simplified to just split each chunk into lines and call {err,out}LineReceived for each line. :runner:

## Documentation ##

* Document naming conventions (below) in the style guide, make sure everything adheres to those conventions
  * interCaps for Python, CoffeeScript function names
  * In the Data API, each resource has an id named after the resource type, e.g., ``masterid`` or ``builderid``.
    @TODO: actually it would make things much easier for webui to have it named ``id``
  * In the DB API, each result field has an ``id`` key.
* The how-to guides for the Data API (writing new resource types, endpoints, etc.) should be moved to a new file
* The tour must be upgraded to cover the new web UI.

## Asynchronous Steps ##

In 0.8.x, build steps are *very* synchronous.
Nine introduces "new-style" steps that call methods asynchronously and do not expect easy access to the full text of logfiles.
However, there's also substantial work in place to maintain backward compatibility - at least temporarily - for old-style steps.
This project is mostly in Dustin's head.
Here are the remaining bits:

* implement new-style compatibility on master, as well
  * just return defer.succeed(..); no need for wrappers for old-style steps
  * include enough checks that users can be confident their new-style steps are OK

* change backend to use data API
  * persist properties at build or step finish
  * change addLog to return a ProcessLog instance

* ensure that new-style steps don't see any removed methods or old behaviors
  * all of the stuff listed as removed in the relnotes
  * `createSummary`, `log_eval_func`, among others

* rewrite steps to new style
  * but not ShellCommand, yet, since user classes derive from it
  * merge rewrites to master
  * remove `step_status` for statistics

## Data API ##

### Other Resource-Type Related Tasks ###

* ``addBuildset`` currently sends messages about buildrequests directly.
  It should, instead, coordinate with the buildrequests resource type to do so.
* Similarly, `addBuildset` often creates source stamps.
  Messages should be sent when this occurs.
* Add support for uids to the change resource type :runner:
* Consider importing build pickles into the new DB. :runner:
* Implement compression in log chunks - implement ``compressLog`` to re-split logs into larger chunks and compress them; implement decompression, and handle the case where chunks overlap during the compression process :runner:

### Misc Data API Work ###

* Add proper messages about build requests and buildsets to the build request distributor
  * claiming build requests
  * unclaiming build requests
  * completing build requests
  * completing buildsets
* Make sure that the arguments to `addChange` are flexible and compatible: http://trac.buildbot.net/ticket/2378 :runner:
* addBuildset should take a list of builder IDs, rather than names :runner:
* REST stuff:
  * Create links with relations (`rel=..`). :runner:
* If several rtypes have `_db2data` functions or similar (so far masters and changes both do), then make that an idiom and document it.
* Move the methods of BuilderControl to update methods of the Builder resouce type (or other places as appropriate), and add control methods where appropriate.
  In particular, implement `rebuildBuild` properly.
* Use DateTimes everywhere :runner:
* Ensure that all foreign id's in the Data API are named using their full name (e.g., ``sourcestampid`` and not ``ssid``).
as per jsonapi spec, this does not include the self-id (so, ``id``, not ``builderid``, is a field of a builder resource). :runner:
* Ensure that resources are consistent in their handling of embedded objects vs. ids/links.
* follow more jsonapi spec concerning links. Better use the id only version. developer will then use the spec to know how to fetch it.
ex from jsonapi spec:
{
  "posts": [{
    "id": "1",
    "title": "Rails is Omakase",
    "links": {
      "author": "9",
      "comments": [ "5", "12", "17", "20" ]
    }
  }]
}
* Remove `listBuilderNames` and `getPendingBuildTimes` methods from BaseScheduler when they are no longer used.
* Add messages to the scheduler resource type, one for each possible change in scheduler status. :runner:
* Add a means to enumerate builds *previous* to a given build, using flexible criteria.
  Something like ``/build/1234/previous?lib:branch=foo&builder=bar&count=3`` to get the three builds before 1234 with branch ``foo`` in the ``lib`` codebase, on builder ``bar``.
  This is to address http://trac.buildbot.net/ticket/2431.
* Represent buildset properties (perhaps by adding a 'propertyset' rtype, flexible enough to serve for buildsets and builds).
  Same for builds. :runner:
* Rewrite all message and endpoint names in the Data API documentation to use ``{var}`` instead of ``$var`` :runner:
* Check that all Data API update methods have fake implementations, and that those fake implementations have the same signature as the real implementation.
* Steps' URLs should be stored as JSON objects giving both a title and a URL. :runner:
* Validate messages using the same system as used to validate resource types
* the fake self.master.mq.startConsuming should verify that all of its arguments are strings :runner:
* Type verificatoin in the fake self.master.mq.produce is currently commented out, since the first element in the routing key does not correctly identify the resource type.
  It's possible that the last or second-to-last element *does* reliably identify the type, in which case this verification can be reinstated.
  Whether this is possible depends on whether we continue to send multiple messages for each event.

## Missing Functionality ##

* Builds' status strings are not handled like they were in the 0.8.x version.
  The old handling should be characterized and, roughly at least, reproduced.

## Testing ##

The BaseScheduler's addBuildsetForXxx methods should have their signatures checked against the corresponding fakes.

## Status Rewrites ##

The following will need to be rewritten:

* IRC (words.py) :runner:
* WebStatus (already in progress with buildbot-www)
* MailNotifier.
  Note that the tests for MailNotifier mock a lot of things out - incorrectly, now.
  So don't trust the tests!
* Tinderbox (maybe)
* `status_gerrit`
* `status_push` (maybe)

## Web ##

### Javascript ###

* Convert tabs to spaces
* Verify licensing for Bootstrap

### Javascript Testing ###

We need a means to unit-test the JavaScript frontend.

Testing javascript and json api interaction is tricky. Few design principles:
* Stubbing the data api in JS can only be made automatic, by reusing the same spec that the python tests are already using.
* ensure tests run either in dev mode, and prod mode. dev mode is much easier to debug, but the step of minification
  adds some small deviation which makes important to unit test.
* Run JS inside trial environment is difficult. txghost.py method has been experimented, and has several drawbacks.
  - ghost is based on webkit which in turn is based on qt. The qtreactor had licence issue and is not well supported in twisted. So there is a
    hack in txghost trying to run the qt event loop at the same time as the twisted event loop.
  - better solution would be to run ghost in its own process, and have minimal RPC to control it. RPC between twisted and qt looks complicated.
  - installing pyqt/webkit inside virtualenv is tricky. You need to manually copy some of the .so libraries inside the sandbox
  - ghost is not very well supported/known in the JS community
* better option has been discussed:
  - let the JS test suite be entirely JS driven, and not python trial driven + JS assertion, like originally though
  - angularJS comes with a very well though test framework (Karma + Jasmine). We should use it.
  - For E2E tests, there is a angularJS solution which is pure E2E (need a real full blown master)
  - Intermediate solution testing the whole UI against the fake data API has to be investigated.
  - We have not found (yet) solution for testing the templates appart from E2E.

### REST API ###

* Use plurals in path elements (/changes/NNN rather than /change/NNN) :runner:
* Return dates as strings :runner:
* Add cache headers to the HTTP server, based on information encoded in the resource types regarding immutability and speed of change. :runner:

### Documentation ###

* Document writing plugins, and create an example plugin project on GitHub.

### Localization ###

AngularJS ecosystem has ngTranslate project, which makes i18n relatively easy.

### Setup ###

`buildbot create_master` and `buildbot upgrade_master` need to be upgraded to handle whatever setup is required for the new web service.
The upgrade process should make whatever modifications are required, or at least tell the user what directories are no longer used, e.g., templates.

## Database ##

### Schema Changes ###

* Remove ``is_dir`` from the changes table (and ignore/remove it everywhere else)
* Add ``changesources`` :runner:
* add a parent-child 1-N relationship table for triggered and promoted build
  Should that be buildid 1-N buildsetid or buildid 1-N buildid?

### DB API Changes ###

* Use None/NULL, not -1, as the "no results yet" sentinel value in buildsets and buildrequests :runner:
* Make `completeBuildSet` return true if the database claims to have updated the row, and use that to narrow the race condition in `maybeBuildsetComplete`
* Use sa.Text instead of sa.String(LEN), so we have unlimited-length strings.
  Where indexes -- especially unique indexes -- are required on these columns, add sha1 hash columns and index those.
  Among other advantages, this will allow MySQL databases to use the vastly superior InnoDB table type.
* Rather than naming builders, build requests should use a foreign key to reference the builders table. :runner:
* Convert master, builder, and scheduler names to identifiers, removing use of hashes :runner:

### Documentation ###

* Document Buildbot's behavior for a DBA: isolation assumptions, dependencies on autogenerated IDs, read-after-write expectations, buildrequest claiming, buildset completion detection

### Miscellaneous ###

* Look carefully at race conditions around masters being marked inactive
* Now that schedulers don't give lists of changes to addBuildset, there's no need to keep a list of important/unimportant changes; just state.

## Later ##

This section can hold tasks that don't need to be done by 0.9.0, but shouldn't be forgotten, and might be implemented sooner if convenient.

### MQ ###

The MQ layer currently only has a simple (single-master) implementation.  We should have some or all of

* AMQP
* AMP-based master-to-master communication (full mesh, with every master talking to every other master)
* ZeroMQ

### Data API ###

* Add identifiers for builders (url-component safe strings), and allow use of those in place of integer IDs in data API paths.
  For example, external users might find it easier to look at a request queue with `/builder/smoketest/requests` rather than `/buidler/12/requests`.
* Specify ``slaves`` instead of a single slave for builds, to leave open the possibility of a build running on zero or multiple slaves.

### Infrastructure ###

* Use some fancy algorithms to delay message transmission until the data is known-good in the database, for cases where the underlying database is asynchronously replicated.
* Make the DB API a sub-component of the Data API, so that the two can be more tightly coupled (allowing for more effective filtering, sorting, and pagination) and so that it is clear the DB API should not be used outside of teh Data API implementation.  This will also permit changes to the DB API with fewer compatibility concerns.

### Documentation ###

* Document how to write a scheduler: the ``addBuildsetForXxx`` methods, as well as the proper procedure for listening for changes.
