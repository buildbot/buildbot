angular.module('app').controller 'builderController',
['$log', '$scope', '$location', 'buildbotService', '$stateParams'
    ($log, $scope, $location, buildbotService, $stateParams) ->
        builder = buildbotService.one('builder', $stateParams.builder)
        builder.bind($scope, 'builder')
        builder.all('forceschedulers').bind($scope, 'forceschedulers')
        builder.all('build').bind($scope, 'builds')
]
