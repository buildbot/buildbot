class Changes extends Controller
    constructor: ($scope, dataService) ->
        data = dataService.open()
        data.closeOnDestroy($scope)
        @list = data.getChanges(limit: 40, order: '-when_timestamp').getArray()
