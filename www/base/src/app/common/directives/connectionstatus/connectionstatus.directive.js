/*
 * decaffeinate suggestions:
 * DS102: Remove unnecessary code created because of implicit returns
 * Full docs: https://github.com/decaffeinate/decaffeinate/blob/master/docs/suggestions.md
 */
class connectionstatus {
    constructor(RecursionHelper) {
        return {
            replace: true,
            restrict: 'E',
            scope: {},
            template: require('./connectionstatus.tpl.jade'),
            compile: RecursionHelper.compile,
            controller: '_connectionstatusController'
        };
    }
}

class _connectionstatus {
    constructor($scope, $timeout) {
        $scope.alertenabled = false;
        $scope.connectionlost = false;
        $scope.$on("mq.lost_connection", function() {
            $scope.connectionlost = true;
            return $scope.alertenabled = true;
        });

        $scope.$on("mq.restored_connection", function() {
            $scope.connectionlost = false;
            $scope.alertenabled = true;
            return $timeout(() => $scope.alertenabled = false
            , 4000);
        });
    }
}


angular.module('common')
.directive('connectionstatus', ['RecursionHelper', connectionstatus])
.controller('_connectionstatusController', ['$scope', '$timeout', _connectionstatus]);
