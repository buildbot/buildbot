This package contains the JavaScript UI for Buildbot.

This is a fairly typical Dojo application, and should be familiar to users of that 
framework. See the Buildbot documentation for a quick start guide and links to the
relevant Dojo documentation.

Because Buildbot is primarily a Python application, this package is designed to be
installed using the Python packaging system.  After performing a typical Dojo build,
the 'build.sh' script wraps that build into a Python distribution tarball, including
a very small Python wrapper allowing Buildbot to find the built files.

Libraries
=========

Several libraries are included in the source tree using git submodules, and
bundled into the built package using the Dojo builder.

Use 'git submodules' to list the origin, revision, and tag for each.

Notes
=====

Moment.js does not play well with Dojo.  The version used here is forked and
has some patches applied to work better,  but not perfectly, with the Dojo
build system.  In particular, while moment.js itself works fine, none of its
language files are available.
