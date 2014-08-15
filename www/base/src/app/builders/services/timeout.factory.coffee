class scopeTimeout extends Factory
    constructor: ($timeout) ->
        return ($scope, fn, delay, invokeApply) ->
            ret = $timeout(fn, delay, invokeApply)
            $scope.$on '$destroy', ->
                $timeout.cancel(ret)
            return ret