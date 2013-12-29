angular.module('app').controller 'buildersController',
['$log', '$scope', '$location', 'buildbotService'
    ($log, $scope, $location, buildbotService) ->

        buildbotService.all('builder').bind $scope,
            onchild: (builder) ->
                builder.all('buildslave').bind $scope,
                    dest: builder
                builder.some('build', {limit:20, order:"-number"}).bind $scope,
                    dest: builder

]
