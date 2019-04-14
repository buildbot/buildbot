class StepState {
    constructor($stateProvider) {

        // Name of the state
        const name = 'step';

        // Configuration
        const cfg = {
            tabid: 'builders',
            pageTitle: _.template("Buildbot: build <%= build %> step: <%= step %>")
        };

        // Register new state
        $stateProvider.state({
            controller: `${name}Controller`,
            templateUrl: `views/${name}.html`,
            name,
            url: '/builders/:builder/builds/:build/steps/:step',
            data: cfg
        });
    }
}


angular.module('app')
.config(['$stateProvider', StepState]);
