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

module.exports =
    name: 'grid_view'
    dir: build: 'buildbot_grid_view/static'
    bower:
        testdeps:
            # vendors.js includes jquery, angularjs, etc in the right order
            "guanlecoja-ui":
                version: '~1.6.0'
                files: ['vendors.js', 'scripts.js']
            "angular-mocks":
                version: '~1.5.3'
                files: "angular-mocks.js"
            'buildbot-data':
                version: '~2.2.0'
                files: 'dist/buildbot-data.js'

    karma:
        # we put tests first, so that we have angular, and fake app defined
        files: ["tests.js", "scripts.js", 'fixtures.js']
