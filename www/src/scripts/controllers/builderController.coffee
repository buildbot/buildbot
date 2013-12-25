angular.module('app').controller 'builderController',
['$log', '$scope', '$location', 'buildbotService', '$stateParams',
    ($log, $scope, $location, buildbotService, $stateParams) ->
        builder = buildbotService.one('builder', $stateParams.builder)
        builder.bind($scope)
        builder.all('forcescheduler').bind($scope)
        builder.some('build', {limit:20, order:"-number"}).bind($scope)
        builder.some('buildrequest', {claimed:0}).bind($scope)
]
