class Changes extends Controller
    constructor: ($log, $scope, dataService) ->
        opened = dataService.open($scope)
        $scope.changes = opened.getChanges(limit:50, order:'-when_timestamp').getArray()
