angular.module('app').controller 'buildersController', ['$log', '$scope', '$location', 'buildbotService'
    ($log, $scope, $location, buildbotService) ->
        $scope.builders = []
        $scope.gridOptions =
            data: 'builders'
        buildbotService.populateScope $scope, 'builders', 'builder', 'builder'
]