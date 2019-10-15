/*
 * decaffeinate suggestions:
 * DS207: Consider shorter variations of null checks
 * Full docs: https://github.com/decaffeinate/decaffeinate/blob/master/docs/suggestions.md
 */
class Masters {
    constructor($scope, dataService, dataGrouperService, resultsService, $stateParams) {
        _.mixin($scope, resultsService);
        $scope.maybeHideMaster = function(master) {
            if ($stateParams.master != null) {
                return master.masterid !== +$stateParams.master;
            }
            return 0;
        };
        const data = dataService.open().closeOnDestroy($scope);
        $scope.masters = data.getMasters();
        $scope.builders = data.getBuilders();
        const workers = data.getWorkers();

        const builds = data.getBuilds({limit: 100, order: '-started_at'});
        dataGrouperService.groupBy($scope.masters, builds, 'masterid', 'builds');
        dataGrouperService.groupBy($scope.masters, workers, 'masterid', 'workers', 'connected_to');
    }
}


angular.module('app')
.controller('mastersController', ['$scope', 'dataService', 'dataGrouperService', 'resultsService', '$stateParams', Masters]);
