angular.module('buildbot.changes').controller 'changesController',
['$log', '$scope', 'buildbotService'
    ($log, $scope, buildbotService) ->
        buildbotService.all('changes').bind($scope)
]
