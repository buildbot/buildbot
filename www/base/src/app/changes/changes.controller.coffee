class Changes extends Controller
    constructor: ($log, $scope, dataService) ->
        data = dataService.open($scope)
        $scope.changes = data.getChanges(limit:50, order:'-when_timestamp').getArray()
