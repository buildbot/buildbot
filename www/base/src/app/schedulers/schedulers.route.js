class SchedulersState {
    constructor($stateProvider) {

        // Name of the state
        const name = 'schedulers';

        // Configuration
        const cfg = {
            group: "builds",
            caption: 'Schedulers'
        };

        // Register new state
        $stateProvider.state({
            controller: `${name}Controller`,
            template: require('./schedulers.tpl.jade'),
            name,
            url: '/schedulers',
            data: cfg
        });
    }
}


angular.module('app')
.config(['$stateProvider', SchedulersState]);
