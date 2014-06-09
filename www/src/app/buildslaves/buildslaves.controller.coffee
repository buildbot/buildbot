angular.module('buildbot.buildslaves').controller 'buildslavesController',
['$scope', 'buildbotService',
    ($scope, buildbotService) ->

        buildbotService.all('buildslaves').bind($scope)

]
