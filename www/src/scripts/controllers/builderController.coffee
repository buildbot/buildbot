angular.module('app').controller 'builderController',
['$log', '$scope', '$location', 'buildbotService', '$routeParams'
    ($log, $scope, $location, buildbotService, $routeParams) ->
        builder = buildbotService.one('builder', $routeParams.builder)
        builder.bind($scope, 'builder')
        builder.all('build').bind($scope, 'builds')
]
