angular.module('buildbot.schedulers').config ['$stateProvider',
    ($stateProvider) ->

        # Name of the state
        name = 'schedulers'

        # Configuration
        cfg =
            tabid: name
            tabhash: "##{name}"
            caption: 'Schedulers'

        # Register new state
        state =
            controller: "#{name}Controller"
            templateUrl: "views/#{name}.html"
            name: name
            url: '/schedulers'
            data: cfg

        $stateProvider.state(state)
]