angular.module('app').controller 'buildersController',
['$log', '$scope', '$location', 'buildbotService'
    ($log, $scope, $location, buildbotService) ->
        buildbotService.all('builder').bind($scope, 'builders')
]
