angular.module('buildbot.masters').config ['$stateProvider',
    ($stateProvider) ->

        # Name of the state
        name = 'masters'

        # Configuration
        cfg =
            tabid: name
            tabhash: "##{name}"
            caption: 'Build Masters'

        # Register new state
        state =
            controller: "#{name}Controller"
            templateUrl: "views/#{name}.html"
            name: name
            url: '/masters'
            data: cfg

        $stateProvider.state(state)
]