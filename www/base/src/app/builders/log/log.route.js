class State {
    constructor($stateProvider) {

        // Name of the state
        const name = 'log';

        // Configuration
        const cfg = {
            tabid: 'builders',
            pageTitle: _.template("Buildbot: log: <%= log %>")
        };

        // Register new state
        const state = {
            controller: `${name}Controller`,
            templateUrl: `views/${name}.html`,
            name,
            url: '/builders/:builder/builds/:build/steps/:step/logs/:log?jump_to_line',
            data: cfg
        };

        $stateProvider.state(state);
    }
}


angular.module('app')
.config(['$stateProvider', State]);