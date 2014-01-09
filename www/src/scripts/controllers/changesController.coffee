angular.module('app').controller 'changesController',
['$log', '$scope', 'buildbotService'
    ($log, $scope, buildbotService) ->
        buildbotService.all('change').bind($scope)
]
