angular.module('buildbot.builders').controller 'logController',
['$scope', 'buildbotService', '$stateParams'
    ($scope, buildbotService, $stateParams) ->
        buildbotService.bindHierarchy($scope, $stateParams, ["builders", "builds", 'steps', 'logs'])
]
