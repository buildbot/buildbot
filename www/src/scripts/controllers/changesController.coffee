angular.module('app').controller 'changesController', ['$log', '$scope', 'buildbotService'
    ($log, $scope, buildbotService) ->
        buildbotService.populateScope $scope, 'changes', 'change', 'change'
]