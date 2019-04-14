/*
 * decaffeinate suggestions:
 * DS102: Remove unnecessary code created because of implicit returns
 * Full docs: https://github.com/decaffeinate/decaffeinate/blob/master/docs/suggestions.md
 */
class scopeTimeout {
    constructor($timeout) {
        return function($scope, fn, delay, invokeApply) {
            const ret = $timeout(fn, delay, invokeApply);
            $scope.$on('$destroy', () => $timeout.cancel(ret));
            return ret;
        };
    }
}

angular.module('app')
.factory('scopeTimeout', ['$timeout', scopeTimeout]);
