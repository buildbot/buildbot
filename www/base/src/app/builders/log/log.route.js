class LogState {
    constructor($stateProvider, config) {

        // Name of the state
        const name = 'log';

        // Configuration
        const cfg = {
            tabid: 'builders',
            pageTitle: _.template(`${config.title}: log: <%= log %>`)
        };

        // Register new state
        const state = {
            controller: `${name}Controller`,
            template: require('./log.tpl.jade'),
            name,
            url: '/builders/:builder/builds/:build/steps/:step/logs/:log?jump_to_line',
            data: cfg
        };

        $stateProvider.state(state);
    }
}


angular.module('app')
.config(['$stateProvider', 'config', LogState]);
