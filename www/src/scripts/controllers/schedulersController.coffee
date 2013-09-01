angular.module('app').controller 'schedulersController',
['$log', '$scope', '$location', 'buildbotService', '$routeParams'
    ($log, $scope, $location, buildbotService, $routeParams) ->
        buildbotService.all('scheduler').getList().then (schedulers) ->
            $scope.schedulers = schedulers
]
