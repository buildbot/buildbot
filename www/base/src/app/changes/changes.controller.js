class Changes {
    constructor($log, $scope, dataService, bbSettingsService,
        $location, $rootScope) {
        $scope.settings = bbSettingsService.getSettingsGroup("Changes");
        $scope.$watch('settings', () => bbSettingsService.save()
        , true);
        const changesFetchLimit = $scope.settings.changesFetchLimit.value;

        const data = dataService.open().closeOnDestroy($scope);
        //  unlike other order, this particular order by changeid is optimised by the backend
        $scope.changes = data.getChanges({limit: changesFetchLimit, order:'-changeid'});
    }
}


angular.module('app')
.controller('changesController', ['$log', '$scope', 'dataService', 'bbSettingsService', '$location', '$rootScope', Changes]);
