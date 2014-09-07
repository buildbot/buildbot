What Is It?
===========

BuildBot Watcher is a `Trac <http://trac.edgewall.org>`_ plugin.
It watches a BuildBot status webserver and incorporates build information into the standard Trac timeline.

Prereqs
=======

For the Trac site
-----------------

This plugin does not require anything other than Trac 0.11+.
It makes use of the standard Trac CSS classes, so it will theme appropriately.

For the BuildMaster
-------------------

For now, you'll need to run a BuildBot using my patched XML-RPC server.

::

    git clone git://github.com/djmitche/buildbot.git buildbot
    cd buildbot
    git pull git://github.com/rbosetti/buildbot.git

Installation
============

Follow the standard fetch, cook, copy procedure:

::

    git clone git://github.com/rbosetti/buildbot.git buildbot
    cd buildbot
    python setup.py bdist_egg
    cp dist/*.egg /path/to/trac/env/plugins
