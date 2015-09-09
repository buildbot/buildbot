class Workers extends Controller
    constructor: ($scope, dataService) ->
        opened = dataService.open()
        opened.closeOnDestroy($scope)
        # TODO: show builder names related to one worker after cache function
        #       of dataService has been finished.
        @list = opened.getBuildworkers().getArray()
