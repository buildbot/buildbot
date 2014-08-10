class Log extends Controller
    ($scope, buildbotService, $stateParams) ->
        buildbotService.bindHierarchy($scope, $stateParams, ["builders", "builds", 'steps', 'logs'])