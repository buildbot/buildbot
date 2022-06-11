class BuilderState {
    constructor($stateProvider, config) {

        // Name of the state
        const name = 'builder';

        // Configuration
        const cfg = {
            tabid: 'builders',
            pageTitle: _.template(`${config.title}: builder <%= builder %>`)
        };

        // Register new state
        const state = {
            controller: `${name}Controller`,
            template: require('./builder.tpl.jade'),
            name,
            url: '/builders/:builder?numbuilds',
            data: cfg
        };

        $stateProvider.state(state);
    }
}


angular.module('app')
.config(['$stateProvider', 'config', BuilderState]);
