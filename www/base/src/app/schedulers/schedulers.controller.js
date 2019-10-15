/*
 * decaffeinate suggestions:
 * DS102: Remove unnecessary code created because of implicit returns
 * Full docs: https://github.com/decaffeinate/decaffeinate/blob/master/docs/suggestions.md
 */
class schedulers {
    constructor($log, $scope, $location, dataService) {
        const data = dataService.open().closeOnDestroy($scope);
        $scope.schedulers = data.getSchedulers();

        $scope.change = function(s) {
            const newValue = s.enabled;
            const param = {enabled: newValue};
            return dataService.control('schedulers', s.schedulerid, 'enable', param);
        };
    }
}


angular.module('app')
.controller('schedulersController', ['$log', '$scope', '$location', 'dataService', schedulers]);
