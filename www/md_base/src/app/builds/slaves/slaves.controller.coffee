class Slaves extends Controller
    constructor: ($scope, dataService) ->
        opened = dataService.open()
        opened.closeOnDestroy($scope)
        # TODO: show builder names related to one slave after cache function
        #       of dataService has been finished.
        @list = opened.getBuildslaves().getArray()
