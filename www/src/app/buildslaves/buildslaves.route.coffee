angular.module('buildbot.buildslaves').config ['$stateProvider',
    ($stateProvider) ->

        # Name of the state
        name = 'buildslaves'

        # Configuration
        cfg =
            tabid: name
            tabhash: "##{name}"
            caption: 'Build Slaves'

        # Register new state
        state =
            controller: "#{name}Controller"
            templateUrl: "views/#{name}.html"
            name: name
            url: '/buildslaves'
            data: cfg

        $stateProvider.state(state)
]