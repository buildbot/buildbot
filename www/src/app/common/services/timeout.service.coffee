angular.module('app').factory 'scopeTimeout',
['$log', '$timeout', ($log, $timeout) ->
    return ($scope, fn, delay, invokeApply) ->
        ret = $timeout(fn, delay, invokeApply)
        $scope.$on '$destroy', ->
            $timeout.cancel(ret)
        return ret
]
