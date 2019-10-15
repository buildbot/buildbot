class ChangeBuildsController {
    constructor($scope, dataService, bbSettingsService, $stateParams, resultsService, $interval, restService) {

        _.mixin($scope, resultsService);
        $scope.settings = bbSettingsService.getSettingsGroup('ChangeBuilds');
        $scope.$watch('settings', () => bbSettingsService.save()
        , true);
        const buildsFetchLimit = $scope.settings.buildsFetchLimit.value;

        const dataAccessor = dataService.open().closeOnDestroy($scope);
        $scope.builders = dataAccessor.getBuilders();

        const changeId = $scope.changeId = $stateParams.changeid;

        dataAccessor.getChanges(changeId).onNew = function(change) {
            $scope.change = change;
        }

        const getBuildsData = function() {
            let requestUrl = `changes/${changeId}/builds`;
            if (!buildsFetchLimit == '') {
                requestUrl = `changes/${changeId}/builds?limit=${buildsFetchLimit}`;
            }
            restService.get(requestUrl).then((data) => {
                $scope.builds = data.builds;
            });
        }

        getBuildsData();

        const stop = $interval(() => {
            getBuildsData();
        }, 5000);

        $scope.$on('$destroy', () => $interval.cancel(stop));
    }
}

angular.module('app')
.controller('changebuildsController', ['$scope', 'dataService', 'bbSettingsService', '$stateParams', 'resultsService', '$interval', 'restService', ChangeBuildsController]);
