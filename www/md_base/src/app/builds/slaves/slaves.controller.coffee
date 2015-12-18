class Slaves extends Controller
    constructor: ($scope, dataService) ->
        data = dataService.open()
        data.closeOnDestroy($scope)
        # TODO: show builder names related to one slave after cache function
        #       of dataService has been finished.
        @list = data.getBuildslaves().getArray()
