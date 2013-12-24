angular.module('app').controller 'builderController',
['$log', '$scope', '$location', 'buildbotService', '$stateParams',
    ($log, $scope, $location, buildbotService, $stateParams) ->
        builder = buildbotService.one('builder', $stateParams.builder)
        builder.bind($scope)
        builder.all('forceschedulers').bind($scope)
        builder.all('build').bind $scope,
            dest_key:'builds'
        builder.all('buildrequest').bind $scope,
            dest_key:'buildrequests'
]
