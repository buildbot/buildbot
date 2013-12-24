angular.module('app').controller 'buildersController',
['$log', '$scope', '$location', 'buildbotService'
    ($log, $scope, $location, buildbotService) ->

        buildbotService.all('builder').bind $scope,
            onchild: (builder) ->
                console.log builder
                builder.all('buildslave').bind $scope,
                    dest: builder
                builder.all('build').bind $scope,
                    dest: builder
                    queryParams: {limit:20, order:"-number"}

]
