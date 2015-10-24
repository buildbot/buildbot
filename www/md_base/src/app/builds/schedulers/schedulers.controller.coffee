class Schedulers extends Controller
    constructor: ($scope, dataService) ->
        data = dataService.open()
        data.closeOnDestroy($scope)
        @list = data.getSchedulers().getArray()
