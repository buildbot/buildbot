# This file is part of Buildbot.  Buildbot is free software: you can
# redistribute it and/or modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation, version 2.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51
# Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Copyright Buildbot Team Members

def setup_bbcfg_xref(app):
    """
    Set up a 'cfg' cross reference type, so that Buildbot master.cfg
    configuration parameters can be referenced and indexed. ::

        .. bbcfg:: schedulers

        Schedulers
        ==========

    and a later reference::

        blah blah blah see :bbcfg:`schedulers` blah
    """

    app.add_crossref_type('bbcfg', 'bbcfg', 'single: BuildMaster Config; %s')

def setup(app):
    setup_bbcfg_xref(app)
