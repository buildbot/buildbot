angular.module('buildbot.builders').config ['$stateProvider',
    ($stateProvider) ->

        # Name of the state
        name = 'log'

        # Configuration
        cfg =
            tabid: 'builders'

        # Register new state
        state =
            controller: "#{name}Controller"
            templateUrl: "views/#{name}.html"
            name: name
            url: '/builders/:builder/build/:build/step/:step/log/:log'
            data: cfg

        $stateProvider.state(state)
]

angular.module('buildbot.builders').controller 'logController',
['$scope', 'buildbotService', '$stateParams'
    ($scope, buildbotService, $stateParams) ->
        buildbotService.bindHierarchy($scope, $stateParams, ["builders", "builds", 'steps', 'logs'])
]
