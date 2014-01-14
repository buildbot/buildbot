angular.module('app').controller 'buildersController',
['$log', '$scope', '$location', 'buildbotService'
    ($log, $scope, $location, buildbotService) ->

        buildbotService.all('builders').bind $scope,
            onchild: (builder) ->
                builder.all('buildslaves').bind $scope,
                    dest: builder
                builder.some('builds', {limit:20, order:"-number"}).bind $scope,
                    dest: builder

]
