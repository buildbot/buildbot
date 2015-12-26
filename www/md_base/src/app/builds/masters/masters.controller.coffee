class Masters extends Controller
    constructor: ($scope, dataService) ->
        data = dataService.open().closeOnDestroy($scope)
        @list = data.getMasters()
