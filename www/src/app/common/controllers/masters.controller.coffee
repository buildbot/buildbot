angular.module('app').controller 'mastersController',
['$log', '$scope', '$location', 'buildbotService',
    ($log, $scope, $location, buildbotService) ->

        buildbotService.all('masters').bind($scope)

]
