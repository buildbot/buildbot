angular.module('app').controller 'stepController',
['$log', '$scope', '$location', 'buildbotService', '$stateParams'
    ($log, $scope, $location, buildbotService, $stateParams) ->
        buildbotService.bindHierarchy($scope, $stateParams, ["builder", "build", 'step'])
        .then ([builder, build, step]) ->
            logs = buildbotService.one("step", step.stepid).all("log")
            logs.bind $scope,
                dest: step,
]
