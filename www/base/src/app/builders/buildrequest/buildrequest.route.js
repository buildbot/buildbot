class BuildRequestState {
    constructor($stateProvider) {

        // Name of the state
        const name = 'buildrequest';

        // Register new state
        const state = {
            controller: `${name}Controller`,
            templateUrl: `views/${name}.html`,
            name,
            data: {},
            url: '/buildrequests/:buildrequest?redirect_to_build'
        };

        $stateProvider.state(state);
    }
}


angular.module('app')
.config(['$stateProvider', BuildRequestState]);
