/*
 * decaffeinate suggestions:
 * DS102: Remove unnecessary code created because of implicit returns
 * Full docs: https://github.com/decaffeinate/decaffeinate/blob/master/docs/suggestions.md
 */
class Pendingbuildrequests {
    constructor($log, $scope, dataService, bbSettingsService, buildersService, restService) {
        $scope.settings = bbSettingsService.getSettingsGroup("BuildRequests");
        const buildrequestFetchLimit = $scope.settings.buildrequestFetchLimit.value;

        const data = dataService.open().closeOnDestroy($scope);
        $scope.buildrequests = data.getBuildrequests({limit: buildrequestFetchLimit, order:'-submitted_at', claimed:false});
        $scope.properties = {};
        $scope.buildrequests.onNew = function(buildrequest) {
            restService.get(`buildsets/${buildrequest.buildsetid}/properties`).then(function(response) {
                buildrequest.properties = response.properties[0];
                _.assign($scope.properties, response.properties[0]);
            });
            buildrequest.builder = buildersService.getBuilder(buildrequest.builderid);
        };
    }
}

angular.module('app')
.controller('pendingbuildrequestsController', ['$log', '$scope', 'dataService', 'bbSettingsService', 'buildersService', 'restService', Pendingbuildrequests]);
