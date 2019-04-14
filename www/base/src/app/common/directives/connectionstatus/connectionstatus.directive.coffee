class connectionstatus
    constructor: (RecursionHelper) ->
        return {
            replace: true
            restrict: 'E'
            scope: {}
            templateUrl: 'views/connectionstatus.html'
            compile: RecursionHelper.compile
            controller: '_connectionstatusController'
        }

class _connectionstatus
    constructor: ($scope, $timeout) ->
        $scope.alertenabled = false
        $scope.connectionlost = false
        $scope.$on "mq.lost_connection", ->
            $scope.connectionlost = true
            $scope.alertenabled = true

        $scope.$on "mq.restored_connection", ->
            $scope.connectionlost = false
            $scope.alertenabled = true
            $timeout ->
                $scope.alertenabled = false
            , 4000


angular.module('common')
.directive('connectionstatus', ['RecursionHelper', connectionstatus])
.controller('_connectionstatusController', ['$scope', '$timeout', _connectionstatus])