/*
 * decaffeinate suggestions:
 * DS102: Remove unnecessary code created because of implicit returns
 * Full docs: https://github.com/decaffeinate/decaffeinate/blob/master/docs/suggestions.md
 */
class Changes {
    constructor($log, $scope, dataService, bbSettingsService) {
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
.controller('changesController', ['$log', '$scope', 'dataService', 'bbSettingsService', Changes]);