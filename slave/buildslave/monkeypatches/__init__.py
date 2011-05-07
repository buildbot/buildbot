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


def patch_bug4881():
    try:
        import twisted
        from twisted.python import versions
    except ImportError:
        # sometimes this is invoked when Twisted is not installed, e.g.,
        # from setup.py; in this case, there's nothing to monkeypatch
        return

    # this bug was only present in Twisted-10.2.0
    if twisted.version == versions.Version('twisted', 10, 2, 0):
        from buildslave.monkeypatches import bug4881
        bug4881.patch()

def patch_all():
    patch_bug4881()
