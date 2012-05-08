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

# concrete verifiers for documented resource types

from buildbot.test.util import typeverifier

verifyChdict = typeverifier.TypeVerifier('chdict',
    attrs = dict(
        changeid='integer',
        author='string',
        files='stringlist',
        comments='string',
        revision='string:none',
        when_timestamp='datetime',
        branch='string:none',
        category='string:none',
        revlink='string:none',
        properties='sourcedProperties',
        repository='string',
        project='string',
        codebase='string',
        is_dir='integer',
        ))

