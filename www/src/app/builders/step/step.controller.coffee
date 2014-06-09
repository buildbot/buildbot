angular.module('buildbot.builders').controller 'stepController',
['$log', '$scope', '$location', 'buildbotService', '$stateParams'
    ($log, $scope, $location, buildbotService, $stateParams) ->
        buildbotService.bindHierarchy($scope, $stateParams, ["builders", "builds", 'steps'])
        .then ([builder, build, step]) ->
            logs = buildbotService.one("steps", step.stepid).all("logs")
            logs.bind $scope,
                dest: step,
]
