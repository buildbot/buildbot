.. _Buildbot-Components:

Buildbot Components
===================

Buildbot is shipped in two components: the *buildmaster* (called ``buildbot`` for legacy reasons) and the *buildslave*.
The buildslave component has far fewer requirements, and is more broadly compatible than the buildmaster.
You will need to carefully pick the environment in which to run your buildmaster, but the buildslave should be able to run just about anywhere.

It is possible to install the buildmaster and buildslave on the same system, although for anything but the smallest installation this arrangement will not be very efficient.


