class Settings {
    constructor($stateProvider, glMenuServiceProvider) {

        // Name of the state
        const name = 'settings';

        // Menu configuration
        glMenuServiceProvider.addGroup({
            name,
            caption: 'Settings',
            icon: 'sliders',
            order: 99
        });

        // Configuration
        const cfg = {
            group: name,
            caption: 'Settings'
        };

        // Register new state
        const state = {
            controller: `${name}Controller`,
            template: require('./settings.tpl.jade'),
            name,
            url: '/settings',
            data: cfg
        };

        $stateProvider.state(state);
    }
}

angular.module('app')
.config(['$stateProvider', 'glMenuServiceProvider', Settings]);
