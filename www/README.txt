This package contains the JavaScript UI for Buildbot.

This is a fairly typical Dojo application, and should be familiar to users of
that framework.  See the Buildbot documentation for a quick start guide and
links to the relevant Dojo documentation.

Because Buildbot is primarily a Python application, this package is designed
to be installed using the Python packaging system.  After performing a typical
Dojo build, the 'build.sh' script wraps that build into a Python distribution
tarball, including a very small Python wrapper allowing Buildbot to find the
built files.

Libraries
=========

The following libraries are included in the source tree, and bundled into the
built package using the Dojo builder.  Each lists the git URL as well as the
branch or tag checked out.  Where HEAD is specified, the version is considered
unimportant; in these cases, consult the SHA1 in the git repository.

https://github.com/dojo/dojo.git - 1.8.1
https://github.com/dojo/dijit.git - 1.8.1
https://github.com/dojo/dojox.git - 1.8.1
https://github.com/dojo/util.git - 1.8.1
https://github.com/kriszyp/xstyle - HEAD
https://github.com/kriszyp/put-selector - HEAD
https://github.com/SitePen/dgrid - HEAD
https://github.com/djmitche/moment - HEAD

Notes
-----

Moment.js does not play well with Dojo.  The version used here is forked and
has some patches applied to work better, but not perfectly, with the Dojo
build system.  In particular, while moment.js itself works fine, none of its
language files are available.
