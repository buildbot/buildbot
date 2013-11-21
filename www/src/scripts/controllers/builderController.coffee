angular.module('app').controller 'builderController',
['$log', '$scope', '$location', 'buildbotService', '$stateParams'
    ($log, $scope, $location, buildbotService, $stateParams) ->
        builder = buildbotService.one('builder', $stateParams.builder)
        builder.bind($scope, 'builder')
        builder.all('forceschedulers').bind($scope, 'forceschedulers')
        builds = builder.all('build')
        builds.bind($scope, 'builds')
]
