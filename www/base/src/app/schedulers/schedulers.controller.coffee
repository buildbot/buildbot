class schedulers
    constructor: ($log, $scope, $location, dataService) ->
        data = dataService.open().closeOnDestroy($scope)
        $scope.schedulers = data.getSchedulers()

        $scope.change = (s) ->
            newValue = s.enabled
            param = enabled: newValue
            dataService.control 'schedulers', s.schedulerid, 'enable', param
                

angular.module('app')
.controller('schedulersController', ['$log', '$scope', '$location', 'dataService', schedulers])