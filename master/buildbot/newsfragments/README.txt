This is the directory for news fragments used by towncrier: https://github.com/hawkowl/towncrier

towncrier has a few standard types of news fragments, signified by the file extension. These are:

.feature: Signifying a new feature.
.bugfix: Signifying a bug fix.
.doc: Signifying a documentation improvement.
.removal: Signifying a deprecation or removal of public API.

The core of the filename can be the fixed issue number of any unique text relative to your work.
Buildbot project does not require a tracking ticket to be made for each contribution even if this is appreciated.

Please point to the bug using syntax: (:bug:`NNN`)
please point to classes using syntax: :py:class:`~buildbot.reporters.http.HttpStatusBase`
