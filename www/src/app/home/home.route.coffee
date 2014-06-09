angular.module('buildbot.home').config ['$stateProvider',
    ($stateProvider) ->

        # Name of the state
        name = 'home'

        # Configuration
        cfg =
            caption: 'Home'

        # Register new state
        state =
            controller: "#{name}Controller"
            templateUrl: "views/#{name}.html"
            name: name
            url: '/'
            data: cfg

        $stateProvider.state(state)
]