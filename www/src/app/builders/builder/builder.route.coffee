angular.module('buildbot.builders').config ['$stateProvider',
    ($stateProvider) ->

        # Name of the state
        name = 'builder'

        # Configuration
        cfg =
            tabid: 'builders'

        # Register new state
        state =
            controller: "#{name}Controller"
            templateUrl: "views/#{name}.html"
            name: name
            url: '/builders/:builder'
            data: cfg

        $stateProvider.state(state)
]