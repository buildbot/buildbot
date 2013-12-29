angular.module('app').controller 'buildslavesController',
['$log', '$scope', '$location', 'buildbotService',
    ($log, $scope, $location, buildbotService) ->

        buildbotService.all('buildslave').bind($scope)

]
