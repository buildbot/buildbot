class Masters extends Controller
    constructor: ($scope, dataService, publicFieldsFilter) ->
        dataService.getMasters().then (masters) ->
            $scope.masters = masters.map (master) -> publicFieldsFilter(master)
