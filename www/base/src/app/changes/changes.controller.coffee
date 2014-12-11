class Changes extends Controller
    constructor: ($log, $scope, buildbotService) ->        
        buildbotService.some('changes', limit:50, order:"-when_timestamp").bind($scope)
