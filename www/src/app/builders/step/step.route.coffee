angular.module('buildbot.builders').config ['$stateProvider',
    ($stateProvider) ->

        # Name of the state
        name = 'step'

        # Configuration
        cfg =
            tabid: 'builders'

        # Register new state
        state =
            controller: "#{name}Controller"
            templateUrl: "views/#{name}.html"
            name: name
            url: '/builders/:builder/build/:build/step/:step'
            data: cfg

        $stateProvider.state(state)
]