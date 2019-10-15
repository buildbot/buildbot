class BuildRequestState {
    constructor($stateProvider) {

        // Name of the state
        const name = 'buildrequest';

        // Register new state
        const state = {
            controller: `${name}Controller`,
            template: require('./buildrequest.tpl.jade'),
            name,
            data: {},
            url: '/buildrequests/:buildrequest?redirect_to_build'
        };

        $stateProvider.state(state);
    }
}


angular.module('app')
.config(['$stateProvider', BuildRequestState]);
