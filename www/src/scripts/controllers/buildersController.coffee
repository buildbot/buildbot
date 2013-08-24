angular.module('app').controller 'buildersController',
['$log', '$scope', '$location', 'buildbotService'
    ($log, $scope, $location, buildbotService) ->
        p = buildbotService.all('builder').bind($scope, 'builders')
        p.then (builders) ->
            # need _.each to create a scope per loop
            _.each $scope.builders, (builder) ->
                builder.all('buildslave').getList().then (slaves) ->
                    builder.slaves = slaves
                builder.all('build').getList().then (builds) ->
                    builder.builds = builds
]
