class StepState {
    constructor($stateProvider, config) {

        // Name of the state
        const name = 'step';

        // Configuration
        const cfg = {
            tabid: 'builders',
            pageTitle: _.template(`${config.title}: build <%= build %> step: <%= step %>`)
        };

        // Register new state
        $stateProvider.state({
            controller: `${name}Controller`,
            template: require('./step.tpl.jade'),
            name,
            url: '/builders/:builder/builds/:build/steps/:step',
            data: cfg
        });
    }
}


angular.module('app')
.config(['$stateProvider','config', StepState]);
