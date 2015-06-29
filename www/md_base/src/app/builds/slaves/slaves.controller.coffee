class Slaves extends Controller
    constructor: ($scope, dataService) ->
        opened = dataService.open()
        opened.closeOnDestroy($scope)
        @list = opened.getBuildslaves().getArray()
