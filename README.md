This is the README for the nine branch; it will be removed when this branch is merged to master.

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

