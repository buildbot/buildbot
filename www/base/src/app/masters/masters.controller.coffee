class Masters extends Controller
    constructor: ($scope, dataService, publicFieldsFilter) ->
        dataService.open().closeOnDestroy($scope).getMasters().getArray().onChange = (masters) ->
            $scope.masters = masters.map (master) -> publicFieldsFilter(master)
