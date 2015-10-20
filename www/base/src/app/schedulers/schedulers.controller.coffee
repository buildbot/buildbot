class schedulers extends Controller
    constructor: ($log, $scope, $location, dataService) ->
        $scope.schedulers = dataService.getSchedulers().getArray()
