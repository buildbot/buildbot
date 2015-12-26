class Schedulers extends Controller
    constructor: ($scope, dataService) ->
        data = dataService.open().closeOnDestroy($scope)
        @list = data.getSchedulers()
