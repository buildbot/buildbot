Contributing to Buildbot
========================

Thank you for contributing to Buildbot!

What appears below is just a quick summary.  See http://trac.buildbot.net/wiki/Development for the full story.

Issues, Bugs, Tickets
---------------------

*We do not use the GitHub Issue Tracker for bugs*

Please file tickets for any bugs you discover at http://trac.buildbot.net.

The GitHub Issue Tracker is enabled only because it is a more usable interface for pull requests.

Patches
-------

Contributions to Buildbot should come as a complete package.  For code changes, tests and documentation updates should be included.  Consider issues of compatibility, flexibility, and simplicity.  Follow the existing Buildbot coding style, and be sure that your changes do not cause warnings from pyflakes.  Patches are best submitted as Github pull requests, but also accepted as patch files attached to Trac tickets, or in attachments sent to the buildbot-devel mailing list.  Patch guidelines are at http://trac.buildbot.net/wiki/SubmittingPatches.

Your contribution must be licensed under the GPLv2, and copyright assignment is not expected (or possible: Buildbot is not a legal entity).  See http://trac.buildbot.net/wiki/LicensingYourContribution for details.

You should run common/validate.sh before sending your patches.

Also you can install our git hook for validating and fixing most common coding style issues

   cp common/hooks/post-commit .git/hooks

Development Tips
----------------

The easiest way to hack on Buildbot is in a virtualenv.  See http://trac.buildbot.net/wiki/RunningBuildbotWithVirtualEnv for a description of how to set up such a thing.
