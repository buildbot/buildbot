angular.module('buildbot.builders').config ['$stateProvider',
    ($stateProvider) ->

        # Name of the state
        name = 'buildrequest'

        # Configuration
        cfg =
            tabid: 'builders'

        # Register new state
        state =
            controller: "#{name}Controller"
            templateUrl: "views/#{name}.html"
            name: name
            url: '/buildrequests/:buildrequest?redirect_to_build'
            data: cfg

        $stateProvider.state(state)
]