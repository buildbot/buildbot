class Changes extends Controller
    constructor: ($log, $scope, dataService) ->
        data = dataService.open().closeOnDestroy($scope)
        #  unlike other order, this particular order by changeid is optimised by the backend
        $scope.changes = data.getChanges(limit:50, order:'-changeid')
