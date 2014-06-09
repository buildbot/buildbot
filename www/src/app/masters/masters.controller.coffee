angular.module('buildbot.masters').controller 'mastersController',
['$scope', 'buildbotService',
    ($scope, buildbotService) ->

        buildbotService.all('masters').bind($scope)

]
