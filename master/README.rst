Buildbot: The Continuous Integration Framework
==============================================

:Site: https://buildbot.net
:Original author: Brian Warner <warner-buildbot @ lothar . com>
:Current maintainer: `The Botherders <https://github.com/buildbot/botherders>`_.

.. contents::
   :local:

Buildbot is an open-source continuous integration framework for automating software build, test, and release processes.

* Buildbot is easy to set up, but very extensible and customizable.
  It supports arbitrary build processes, and is not limited to common build processes for particular languages (e.g., autotools or ant)
* Buildbot supports building and testing on a variety of platforms.
  Developers, who do not have the facilities to test their changes everywhere before committing, will know shortly afterwards whether they have broken the build or not.
* Buildbot allows to track various metrics (warning counts, lint checks, image size, compile time, etc) over time.
* Buildbot has minimal requirements for workers: using virtualenv, only a Python installation is required.
* Workers can be run behind a NAT firewall and communicate with the master.
* Buildbot has a variety of status-reporting tools to get information about builds in front of developers in a timely manner.

Documentation
-------------

See https://docs.buildbot.net/current/ for documentation of the current version of Buildbot.

Docker container
----------------
Buildbot comes with a ready to use docker container available at buildbot/buildbot-master
Following environment variables are supported for configuration:

* ``BUILDBOT_CONFIG_URL``: http url to a config tarball.
    The tarball must be in the .tar.gz format.
    The tarball must contain a directory, which will contain a master.cfg file in it.
    The tarball may contain a twisted.tac file in it, which can be used to configure the twisted logging system (e.g to log in logstash instead of the default stdout).
    The tarball will be extracted in a directory named ``$BUILDBOT_CONFIG_DIR`` in the master directory, and can contain additional python module that the master.cfg can load.
    If ``BUILDBOT_CONFIG_URL`` does not end with .tar.gz, it is considered to be an URL to the direct ``master.cfg``

* ``BUILDBOT_CONFIG_DIR`` directory where to extract the config tarball within the master directory.
  It is important so that you can do relative imports in your master.cfg like it is done in the metabbotcfg (https://github.com/buildbot/metabbotcfg)


Requirements
------------

See https://docs.buildbot.net/current/manual/installation/index.html

Briefly: python, Twisted, Jinja2, simplejson, and SQLite.
Simplejson and SQLite are included with recent versions of Python.

Contributing
-------------

Please send your patches to https://github.com/buildbot/buildbot/

Support
-------

Please send questions, file bugs, etc, on the Buildbot Github project https://github.com/buildbot/buildbot/issues.
Alternatively, write to the buildbot-devel mailing list reachable through https://buildbot.net/.

Copying
-------

Buildbot is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation, version 2.

This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
See the GNU General Public License for more details.

For full details, please see the file named COPYING in the top directory of the source tree.
You should have received a copy of the GNU General Public License along with this program.
If not, see <http://www.gnu.org/licenses/>.
