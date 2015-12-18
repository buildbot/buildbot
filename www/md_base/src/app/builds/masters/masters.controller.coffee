class Masters extends Controller
    constructor: ($scope, dataService) ->
        data = dataService.open()
        data.closeOnDestroy($scope)
        @list = data.getMasters().getArray()
