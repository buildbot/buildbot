class Changes extends Controller
    constructor: ($log, $scope, buildbotService) ->
        buildbotService.all('changes').bind($scope)