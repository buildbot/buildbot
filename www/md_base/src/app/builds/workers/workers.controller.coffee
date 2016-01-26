class Workers extends Controller
    constructor: ($scope, dataService) ->
        data = dataService.open().closeOnDestroy($scope)
        # TODO: show builder names related to one worker after cache function
        #       of dataService has been finished.
        @list = data.getWorkers()
