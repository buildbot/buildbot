angular.module('buildbot.changes').config ['$stateProvider',
    ($stateProvider) ->

        # Name of the state
        name = 'changes'

        # Configuration
        cfg =
            tabid: name
            tabhash: "##{name}"
            caption: 'Last Changes'

        # Register new state
        state =
            controller: "#{name}Controller"
            templateUrl: "views/#{name}.html"
            name: name
            url: '/changes'
            data: cfg

        $stateProvider.state(state)
]