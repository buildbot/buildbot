angular.module('app').controller 'builderController',
['$log', '$scope', '$location', 'buildbotService', '$stateParams',
    ($log, $scope, $location, buildbotService, $stateParams) ->
        builder = buildbotService.one('builders', $stateParams.builder)
        builder.bind($scope)
        builder.all('forceschedulers').bind($scope)
        builder.some('builds', {limit:20, order:"-number"}).bind($scope)
        builder.some('buildrequests', {claimed:0}).bind($scope)
]
