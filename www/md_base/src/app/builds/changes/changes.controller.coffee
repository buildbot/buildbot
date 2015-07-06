class Changes extends Controller
    constructor: ($scope, dataService) ->
        opened = dataService.open()
        opened.closeOnDestroy($scope)
        @list = opened.getChanges(limit: 40, order: '-when_timestamp').getArray()
