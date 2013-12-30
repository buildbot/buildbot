What?  This doesn't look like a README!

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

# Project Progress #

At this point, most of the configuration objects (masters, schedulers, builders, etc.) and everything that is in the DB in 0.8.x are ported to the Data API.
The status objects (builds, steps, logs, log chunks) are defined in the DB and Data APIs, and Buildbot inserts data into the DB as builds proceed, as well as updating the legacy status objects.

The new web UI is functional but by no means feature-complete.
See ``master/docs/developer/www.rst`` for more about the UI.

The next steps are:

 * refactor lots of steps to not use deprecated log methods
 * rewrite status listeners
 * stop updating status objects

# Tasks #

There's lots of work do do before we're ready for 0.9.0.
Below are some of those tasks, divided into categories according to how much context is required and how clearly defined the goal is.

If you'd like to help out, please do!
Contact the developers in #buildbot or on the mailing list with any questions.

## "Simple" ##

These are tasks that don't require too much nine-specific context.
You should be able to jump in after reading some related code and documentation.

### Trigger Links ###

In the Trigger step, add links from the triggering step to the triggered builds

### Names for IDs ###

In the Data API, each resource has an id named after the resource type, e.g., ``masterid`` or ``builderid``.
In the DB API, ID's are always named ``id``, since there's generally only one.

It would make things easier for users of the REST API if the Data API provided an 'id' field for the ID of the resource, with links to other resources using longer names like ``masterid``.
This is also in accordance with the JSON API.

In the process, validate that all links to other resources use the full name, e.g., ``sourcestampid``, not something shorter like ``ssid``.

### Documentation Refactoring ###

The how-to guides for the Data API (writing new resource types, endpoints, etc.) should be moved out of ``data.rst`` and into new files, 
The DB API documentation should be broken into multiple files like the Data API.

### Buildset Refactoring ###

``addBuildset`` currently sends messages about buildrequests directly.
It should, instead, coordinate with the buildrequests resource type to do so.

Similarly, `addBuildset` often creates source stamps.
Messages should be sent when this occurs.

The BaseScheduler's addBuildsetForXxx methods should have their signatures checked against the corresponding fakes.

Finally, addBuildset should take a list of builder IDs, rather than their names.
Similarly, rather than naming builders, build requests in the DB should use a foreign key to reference the builders table.

### More Properties ###

Properties are currently omitted in many places in the Data API.
Come up wiht a consistent way to represent properties (perhaps by adding a 'propertyset' rtype, flexible enough to serve for buildsets and builds).

The storage for the properties should also be determined carefully.
A single blob containing all properties for a build set, build, etc., makes it difficult to query for builds with particular properties, which will surely be a common request.

### Step URLs Are Missing Titles ###

We currently store steps' URLs as a list of strings, but URLs are actually tuples of (title, URL), so the format should be adjusted accordingly.

### Validate Messages against resource type definitions ###

Validation for messages is currently based on definitions in ``master/buildbot/test/util/validation.py``, while validation for resource types is based on the resource type definition itself.
Since messages should match resource types, it make sense that message validation should be based on resource type definitions, too.

The wrinkle here is that it's currently difficult to figure out what resource type a message corresponds to.
At one point, the first component of each routing key identified the type, but new topics don't follow this pattern.

### Check startConsuming Arguments ###

The ``startConsuming`` method must be passed only strings.
The fake version of this method should verify that each argument is a string.

### addChange arguments ###

We have gone back and forth over which arguments are accepted for this method -- ``when`` or ``when_timestamp``, for example.
At this point, we should just be flexible about the arguments, and test that flexibility.
See http://trac.buildbot.net/ticket/2378.

### Users for Changes (Sam Kleinman) ###

In the Data API, Changes don't have users, even though that data is in the DB API.
Change users should be included in changes.

### Compress Log Chunks ###

The log chunk support in the DB and Data APIs supports compressing logs after they are created.
However, right now this is a no-op.

Compression is intended to include byte-stream compression, but the major advantage will be in collapsing multiple, small log chunks into larger chunks, resulting in fewer database rows used and thus faster log access.

The compression must be done in such a way that logs can be correctly retrieved at any time.

### Build Request Messages ###

Add proper messages about build requests and buildsets to the build request distributor
  * claiming build requests
  * unclaiming build requests
  * completing build requests
  * completing buildsets

### Scheduler and ChangeSource Messages ###

Add messages to the scheduler and change source resource types, one for each possible change in status.
This will allow users to track which master has a running scheduler.

### Remove Links ###

The Data API does quite a bit of extra work to support links in REST responses, because REST says they're important.
But they're not really that useful, particularly as implemented.

Let's remove them for now.
We can re-add them later when we have a concrete use-case.

### Document the db2data idiom ###

Several Data API resource types have functions and mixins to convert from DB API dictionaries to Data API objects.
This should be documented as an idiom, and all resource types refactored to follow that idiom closely.

### Use plurals ###

REST API path elements are currently singluar, e.g., ``/build/1/step/3``.
Typical REST design suggests plurals, e.g., ``/builds/1/steps/3``.

The change itself isn't too difficult, but updating every use of singular paths may take some work!

### Reduce Buildset Race Condition ###

Make `completeBuildSet` return true if the database claims to have updated the row, and use that to narrow the race condition in `maybeBuildsetComplete`

### Unlimited-length Strings ###

Use sa.Text instead of sa.String(LEN), so we have unlimited-length (well, almost) strings.
Where indexes -- especially unique indexes -- are required on these columns, add sha1 hash columns and index those.
Among other advantages, this will allow MySQL databases to use the vastly superior InnoDB table type.

### Identifiers and Slugs ###

Convert master, builder, changesource, and scheduler names to identifiers, removing use of hashes.
Use slug/name pairs like in logs to allow display names to contain non-identifier characters.

### Document Writing Schedulers ###

Document how to write a scheduler: the ``addBuildsetForXxx`` methods, as well as the proper procedure for listening for changes.

## "Involved" ##

These tasks are more involved in terms of familiarity with new code in this branch, and with development plans.
However, they are reasonably well-defined, so you won't be required to invent a lot of new ideas.

### Support Rebuilding ###

The ``BuilderControl`` ``rebuildBuild`` method allowed users to request a rebuild of a build.
That class and method are gone, but need to be replaced with a Data API control method that can be called from the Web UI.

### Use DateTime Everywhere ###

Currently, the DB API uses DateTime objects and the Data API uses epoch times.
That's silly.
We should use DateTime instances everywhere, with appropriate code in place to transform them to a usable format in JSON output.

### Flexible Build Queries ###

Add a means to enumerate builds *previous* to a given build, using flexible criteria.
Something like ``/build/1234/previous?lib:branch=foo&builder=bar&count=3`` to get the three builds before 1234 with branch ``foo`` in the ``lib`` codebase, on builder ``bar``.
This is to address http://trac.buildbot.net/ticket/2431.

### Cache Headers ###

The HTTP server should provide cache headers for resources, based on information encoded in resource types regarding immutability and speed of change.
For example, log chunks can always be cached indefinitely, as can a finished build.

### Document Plugins ###

Document writing www plugins, and create an example plugin project on GitHub.

### Remove ``is_dir`` ###

This change attribute is no longer used, but is still in the DB.
Remove it and references to it, but leave the ``addChange`` parameter with a deprecation warning.

### Add more MQ backends ###

The MQ layer currently only has a simple (single-master) implementation.  We should have some or all of

* AMQP
* AMP-based master-to-master communication (full mesh, with every master talking to every other master)
* ZeroMQ

## "Complicated" ##

These tasks are complex and there's no clear implementation plan yet.

### Request collapsing ###

*Currently Broken*: Builds for merged requests currently only refer to one of the merged requests.

* Before a build request is added to a non-empty queue, examine each unclaimed build request in that queue.
  If it is compatible with the new request (defined as having matching sourcestamps, except for revision), then claim the old request and immediately complete it with result SKIPPED.

* Allow the same kind of configuration as for merging: global and per-builder, with options True (merge), False (never), and callable (called with two build request dictionaries, and expected to get the rest from the data API).

* Call it "queue collapsing" rather than merging (hat-tip to Mozilla release engineering for the term)

Note that the first bullet here assumes that a more recently-submitted request should be preferred over an older request.

See https://plus.google.com/105883044168332773236/posts/TG8DHus4L4D

### Asynchronous Steps (dustin) ###

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

### Importing old Build Pickles ###

The most likely plan for data from 0.8.x implementations is to ignore it.
However, it would be great for users if data in build pickles could be easily imported into the database.

### Status Receiver Rewrites ###

The following will need to be rewritten:

* IRC (words.py) :runner:
* MailNotifier.
  Note that the tests for MailNotifier mock a lot of things out - incorrectly, now.
  So don't trust the tests!
* `status_gerrit`
* `status_push` (maybe)

### Localization ###

The Web UI should be localized.
AngularJS ecosystem has ngTranslate project, which makes i18n relatively easy.

### Setup ###

`buildbot create_master` and `buildbot upgrade_master` need to be upgraded to handle whatever setup is required for the new web service.
The upgrade process should make whatever modifications are required, or at least tell the user what directories are no longer used, e.g., templates.

### Track Triggered Builds ###

Add a parent-child 1-N relationship table for triggered and promoted build
Should that be buildid 1-N buildsetid or buildid 1-N buildid?

### Coordinate Messages and Data ###

We currently have a DB API which may use a backend DB without read-after-write consistency, due to replication delay.
And we have an MQ API which introduces an unbounded propagation delay in messages.

So it's possible to receive a message about a change, say a build finishing, after which a DB query still shows the build as unfinished.
Likewise, it's possible to see an updated value from a DB query long before the corresponding message arrives.

This causes problems.
For example, a user might want an event for every build triggered for a particular buildset.
The naive approach is to get the list of current builds for that buildset, and subscribe to builds with that buildset in the future.
Given the timing discrepancies, though, this approach may either miss builds for which a message has already been sent but which is not in the DB yet; or double-report a build which is already in the DB but for which the message has not yet been delivered.

I don't have any good solutions to this.

## Later ##

These tasks are far down the road, but things we don't want to forget.

* Remove `listBuilderNames` and `getPendingBuildTimes` methods from BaseScheduler when they are no longer used.

* Builds' status strings are not handled like they were in the 0.8.x version.
  The old handling should be characterized and, roughly at least, reproduced.

* Document Buildbot's behavior for a DBA: isolation assumptions, dependencies on autogenerated IDs, read-after-write expectations, buildrequest claiming, buildset completion detection

* Now that schedulers don't give lists of changes to addBuildset, there's no need to keep a list of important/unimportant changes; just state.
