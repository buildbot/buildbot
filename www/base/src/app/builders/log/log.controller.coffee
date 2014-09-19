class Log extends Controller
    constructor: ($scope, buildbotService, $stateParams) ->
        buildbotService.bindHierarchy($scope, $stateParams, ["builders", "builds", 'steps', 'logs'])
