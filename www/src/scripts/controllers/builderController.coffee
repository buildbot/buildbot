angular.module('app').controller 'builderController',
['$log', '$scope', '$location', 'buildbotService', '$stateParams', 'resultsService',
    ($log, $scope, $location, buildbotService, $stateParams, resultsService) ->
        # make resultsService utilities available in the template
        _.mixin($scope, resultsService)
        builder = buildbotService.one('builders', $stateParams.builder)
        builder.bind($scope)
        builder.all('forceschedulers').bind($scope)
        builder.some('builds', {limit:20, order:"-number"}).bind($scope)
        builder.some('buildrequests', {claimed:0}).bind($scope)
]
