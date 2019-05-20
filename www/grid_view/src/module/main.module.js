// This file is part of Buildbot.  Buildbot is free software: you can
// redistribute it and/or modify it under the terms of the GNU General Public
// License as published by the Free Software Foundation, version 2.
//
// This program is distributed in the hope that it will be useful, but WITHOUT
// ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
// FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
// details.
//
// You should have received a copy of the GNU General Public License along with
// this program; if not, write to the Free Software Foundation, Inc., 51
// Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
//
// Copyright Buildbot Team Members

import 'angular-animate';
import 'guanlecoja-ui';
import 'buildbot-data-js';

class GridState {
    constructor($stateProvider, glMenuServiceProvider, bbSettingsServiceProvider) {
        // Menu configuration
        glMenuServiceProvider.addGroup({
            name: 'grid',
            caption: 'Grid View',
            icon: 'cubes',
            order: 4
        });

        // Register URL routing
        $stateProvider
            .state({
                name: 'grid',
                controller: 'gridController',
                controllerAs: 'C',
                template: require('./grid.tpl.jade'),
                url: '/grid?branch&tag&result',
                reloadOnSearch: false,
                data: {
                    group: 'grid',
                    caption: 'Grid View'
                }
            });

        bbSettingsServiceProvider.addSettingsGroup({
            name: 'Grid',
            caption: 'Grid related settings',
            items: [{
                    type: 'bool',
                    name: 'fullChanges',
                    caption: 'Show avatar and time ago in change details',
                    defaultValue: false
                }
                , {
                    type: 'bool',
                    name: 'leftToRight',
                    caption: 'Show most recent changes on the right',
                    defaultValue: false
                }
                , {
                    type: 'integer',
                    name: 'revisionLimit',
                    caption: 'Maximum number of revisions to display',
                    default_value: 5
                }
                , {
                    type: 'integer',
                    name: 'changeFetchLimit',
                    caption: 'Maximum number of changes to fetch',
                    default_value: 100
                }
                , {
                    type: 'integer',
                    name: 'buildFetchLimit',
                    caption: 'Maximum number of builds to fetch',
                    default_value: 1000
                }
            ]
        });
    }
}


angular.module('grid_view', [
    'ui.router', 'ui.bootstrap', 'ngAnimate', 'guanlecoja.ui', 'bbData'])
.config(['$stateProvider', 'glMenuServiceProvider', 'bbSettingsServiceProvider', GridState]);

require('./grid.controller.js');
