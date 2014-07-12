angular.module('buildbot.builders').config ['$stateProvider',
    ($stateProvider) ->

        # Name of the state
        name = 'step'

        # Configuration
        cfg =
            tabid: 'builders'

        # Register new state
        $stateProvider.state
            controller: "#{name}Controller"
            templateUrl: "views/#{name}.html"
            name: name
            url: '/builders/:builder/build/:build/step/:step'
            data: cfg

]

angular.module('buildbot.builders').controller 'stepController',
['$log', '$scope', '$location', 'buildbotService', '$stateParams'
    ($log, $scope, $location, buildbotService, $stateParams) ->
        buildbotService.bindHierarchy($scope, $stateParams, ["builders", "builds", 'steps'])
        .then ([builder, build, step]) ->
            logs = buildbotService.one("steps", step.stepid).all("logs")
            logs.bind $scope,
                dest: step,
]
