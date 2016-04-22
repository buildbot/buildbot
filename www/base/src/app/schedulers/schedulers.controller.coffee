class schedulers extends Controller
    constructor: ($log, $scope, $location, dataService) ->
        data = dataService.open().closeOnDestroy($scope)
        $scope.schedulers = data.getSchedulers()
