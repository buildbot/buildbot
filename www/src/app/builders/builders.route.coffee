angular.module('buildbot.builders').config ['$stateProvider',
    ($stateProvider) ->

        # Name of the state
        name = 'builders'

        # Configuration
        cfg =
            tabid: name
            tabhash: "##{name}"
            caption: 'Builders'

        # Register new state
        state =
            controller: "#{name}Controller"
            templateUrl: "views/#{name}.html"
            name: name
            url: '/builders'
            data: cfg

        $stateProvider.state(state)
]