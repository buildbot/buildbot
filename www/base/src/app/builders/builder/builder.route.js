class State {
    constructor($stateProvider) {

        // Name of the state
        const name = 'builder';

        // Configuration
        const cfg = {
            tabid: 'builders',
            pageTitle: _.template("Buildbot: builder <%= builder %>")
        };

        // Register new state
        const state = {
            controller: `${name}Controller`,
            templateUrl: `views/${name}.html`,
            name,
            url: '/builders/:builder?numbuilds',
            data: cfg
        };

        $stateProvider.state(state);
    }
}


angular.module('app')
.config(['$stateProvider', State]);