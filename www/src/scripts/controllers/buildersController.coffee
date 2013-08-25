angular.module('app').controller 'buildersController',
['$log', '$scope', '$location', 'buildbotService'
    ($log, $scope, $location, buildbotService) ->
        # todo this wont really work with sse updates.
        # new builders will not be populated with child data
        p = buildbotService.all('builder').bind($scope, 'builders')
        p.then (builders) ->
            # need _.each to create a scope per loop
            _.each $scope.builders, (builder) ->
                builder.all('buildslave').getList().then (slaves) ->
                    builder.slaves = slaves
                builder.getList('build', {complete:false}).then (builds) ->
                    builder.running_builds = builds

        what_it_should_look_like_eventually = ->
            builders = buildbotService.all('builder').bind($scope, 'builders')
            builders.bindChilds('buildslave')
            builders.bindChilds('build', {complete:false}, 'running_builds')
]
