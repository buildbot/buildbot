class connectionstatus extends Directive('common')
    constructor: (RecursionHelper) ->
        return {
            replace: true
            restrict: 'E'
            scope: {data:'='}
            templateUrl: 'views/connectionstatus.html'
            compile: RecursionHelper.compile
            controller: '_connectionstatusController'
        }

class _connectionstatus extends Controller('common')
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
