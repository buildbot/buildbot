angular.module('app').controller 'logController',
['$log', '$scope', '$location', 'buildbotService', '$stateParams'
    ($log, $scope, $location, buildbotService, $stateParams) ->
        buildbotService.bindHierarchy($scope, $stateParams, ["builder", "build", 'step', 'log'])
]
