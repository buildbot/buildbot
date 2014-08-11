Contributing to Buildbot
========================

Thank you for contributing to Buildbot!

What appears below is just a quick summary.  See http://trac.buildbot.net/wiki/Development for the full story.

Issues, Bugs, Tickets
---------------------

*We do not use the GitHub Issue Tracker for bugs*

Please file tickets for any bugs you discover at http://trac.buildbot.net.
It is not necessary to file a bug if you are preparing a patch.

Submitting Patches
------------------

See http://trac.buildbot.net/wiki/SubmittingPatches for the details.

Your contribution must be licensed under the GPLv2, and copyright assignment is not expected.
See http://trac.buildbot.net/wiki/LicensingYourContribution for details.

You should run common/validate.sh before sending your patches.

Also you can install our git hook for validating and fixing most common coding style issues

   cp common/hooks/post-commit .git/hooks

Development Tips
----------------

The easiest way to hack on Buildbot is in a virtualenv.  See http://trac.buildbot.net/wiki/RunningBuildbotWithVirtualEnv for a description of how to set up such a thing.
