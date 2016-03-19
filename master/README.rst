Buildbot: The Continuous Integration Framework
==============================================

:Site: http://buildbot.net
:Original author: Brian Warner <warner-buildbot @ lothar . com>
:Current maintainer: Dustin J. Mitchell <dustin@buildbot.net>

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

See http://docs.buildbot.net/current/ for documentation of the current version of Buildbot.

Requirements
------------

See http://docs.buildbot.net/current/manual/installation.html

Briefly: python, Twisted, Jinja2, simplejson, and SQLite.
Simplejson and SQLite are included with recent versions of Python.

Contributing
-------------

Please send your patches to https://github.com/buildbot/buildbot/

Support
-------

Please send questions, bugs, patches, etc, to the buildbot-devel mailing list reachable through http://buildbot.net/, so that everyone can see them.

Copying
-------

Buildbot is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation, version 2.

This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
See the GNU General Public License for more details.

For full details, please see the file named COPYING in the top directory of the source tree.
You should have received a copy of the GNU General Public License along with this program.
If not, see <http://www.gnu.org/licenses/>.
