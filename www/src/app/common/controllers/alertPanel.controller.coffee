angular.module('app').controller 'alertPanelController',
['$log', '$scope', '$rootScope', '$timeout', 'alert'
    ($log, $scope, $rootScope, $timeout) ->
        $scope.alerts = []
        $scope.closeAlert = (index) ->
            $scope.alerts.splice(index, 1)

        $rootScope.$on 'alert', (ev, p) ->
            console.log ev
            found = false
            $timeout( ->
                for v in $scope.alerts
                    if v.msg is p.msg
                        found = true
                        v.occur ?= 1
                        v.occur += 1
                        v.occur_msg = "(x#{v.occur})"
                if not found
                    $scope.alerts.push p
            , 0)
            $timeout( ->
                for i, v of $scope.alerts
                    if v is p
                        $scope.closeAlert(i)
                null
            , 10000)
]
