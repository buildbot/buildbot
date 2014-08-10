class schedulers extends Controller
    constructor: ($log, $scope, $location, buildbotService) ->
        buildbotService.all('schedulers').bind($scope)