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

# Register new module
class BuildbotGridView extends App
    constructor: ->
        return [
            'ui.router'
            'ui.bootstrap'
            'ngAnimate'
            'guanlecoja.ui'
            'bbData'
        ]

# Register new state
class State extends Config
    constructor: ($stateProvider, glMenuServiceProvider, bbSettingsServiceProvider) ->
        # Menu configuration
        glMenuServiceProvider.addGroup(
            name: 'grid'
            caption: 'Grid View'
            icon: 'cubes'
            order: 4
        )

        # Register URL routing
        $stateProvider
            .state(
                name: 'grid'
                controller: 'gridController'
                controllerAs: 'C'
                templateUrl: 'grid_view/views/grid.html'
                url: '/grid?branch&tag'
                reloadOnSearch: false
                data:
                    group: 'grid'
                    caption: 'Grid View'
            )

        bbSettingsServiceProvider.addSettingsGroup(
            name: 'Grid'
            caption: 'Grid related settings'
            items: [
                    type: 'bool'
                    name: 'compactChanges'
                    caption: 'Hide avatar and time ago from change details'
                    defaultValue: true
                ,
                    type: 'bool'
                    name: 'rightToLeft'
                    caption: 'Show most recent changes on the left'
                    defaultValue: true
                ,
                    type: 'integer'
                    name: 'revisionLimit'
                    caption: 'Maximum number of revisions to display'
                    default_value: 5
                ,
                    type: 'integer'
                    name: 'changeFetchLimit'
                    caption: 'Maximum number of changes to fetch'
                    default_value: 100
                ,
                    type: 'integer'
                    name: 'buildFetchLimit'
                    caption: 'Maximum number of builds to fetch'
                    default_value: 1000
            ]
        )
