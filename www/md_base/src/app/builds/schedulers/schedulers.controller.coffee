class Schedulers extends Controller
    constructor: ($scope, dataService) ->
        opened = dataService.open()
        opened.closeOnDestroy($scope)
        @list = opened.getSchedulers().getArray()
