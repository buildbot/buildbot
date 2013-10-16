angular.module('app').controller 'builderController',
['$log', '$scope', '$location', 'buildbotService', '$stateParams'
    ($log, $scope, $location, buildbotService, $stateParams) ->
        builder = buildbotService.one('builder', $stateParams.builder)
        builder.bind($scope, 'builder').then (builder) ->
            buildbotService.all('forceschedulers').getList().then (schedulers) ->
                filtered_scheds = []
                for scheduler in schedulers
                    if _.contains(scheduler.builder_names, $scope.builder.name)
                        filtered_scheds.push(scheduler)

                $scope.forceschedulers = filtered_scheds
                return null
        builder.all('build').bind($scope, 'builds')
]
