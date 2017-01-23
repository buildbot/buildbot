class Masters extends Controller
    constructor: ($scope, dataService, dataGrouperService, resultsService, $stateParams) ->
        _.mixin($scope, resultsService)
        $scope.maybeHideMaster = (master) ->
            if $stateParams.master?
                return master.masterid != +$stateParams.master
            return 0
        data = dataService.open().closeOnDestroy($scope)
        $scope.masters = data.getMasters()
        $scope.builders = data.getBuilders()
        workers = data.getWorkers()

        builds = data.getBuilds(limit: 100, order: '-started_at')
        dataGrouperService.groupBy($scope.masters, builds, 'masterid', 'builds')
        dataGrouperService.groupBy($scope.masters, workers, 'masterid', 'workers', 'connected_to')
