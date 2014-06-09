angular.module('buildbot.schedulers').controller 'schedulersController',
['$log', '$scope', '$location', 'buildbotService',
    ($log, $scope, $location, buildbotService) ->
        buildbotService.all('schedulers').bind($scope)
 ]
