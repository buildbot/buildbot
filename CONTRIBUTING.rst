Contributing to Buildbot
========================

.. contents::
   :local:

We value your contribution to Buildbot and thank you for it!

If it happens that your contribution is not reviewed within two days, please do not hesitate to remind about it by leaving a comment "Please review this PR".

What appears below is just a quick summary.
See http://trac.buildbot.net/wiki/Development for the full story.

Issues, Bugs, Tickets
---------------------

Please file tickets for any bugs you discover at http://trac.buildbot.net.
It is not necessary to file a bug if you are preparing a patch.

Submitting Patches
------------------

See http://trac.buildbot.net/wiki/SubmittingPatches for the details.

Your contribution must be licensed under the GPLv2, and copyright assignment is not expected.
See http://trac.buildbot.net/wiki/LicensingYourContribution for details.

You should run common/validate.sh before sending your patches.

Also you can install our git hook for validating and fixing most common coding style issues

::

    cp common/hooks/post-commit .git/hooks

Review
------

Buildbot's code-review process is described at http://trac.buildbot.net/wiki/PatchReview.
The important point to know is that Buildbot requires a positive review (adding the "merge-me" label) before a change is eligible to be merged.
While we try to perform reviews in a timely fashion, if your review has lagged for a week or more please do feel free to nag us in whatever way is easiest for you.

Development Tips
----------------

The easiest way to hack on Buildbot is in a virtualenv.
See http://trac.buildbot.net/wiki/RunningBuildbotWithVirtualEnv for a description of how to set up such a thing.
