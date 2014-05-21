angular.module('app').controller 'schedulersController',
['$log', '$scope', '$location', 'buildbotService', '$stateParams'
    ($log, $scope, $location, buildbotService, $stateParams) ->
        buildbotService.all('schedulers').bind($scope)
 ]
