/*
 * decaffeinate suggestions:
 * DS102: Remove unnecessary code created because of implicit returns
 * Full docs: https://github.com/decaffeinate/decaffeinate/blob/master/docs/suggestions.md
 */
class Buildrequestsummary {
    constructor(RecursionHelper) {
        return {
            replace: true,
            restrict: 'E',
            scope: {buildrequestid: '=?'},
            templateUrl: 'views/buildrequestsummary.html',
            compile: RecursionHelper.compile,
            controller: '_buildrequestsummaryController'
        };
    }
}

class _buildrequestsummary {
    constructor($scope, dataService, buildersService, findBuilds, resultsService) {
        _.mixin($scope, resultsService);
        $scope.$watch("buildrequest.claimed", function(n, o) {
            if (n) {  // if it is unclaimed, then claimed, we need to try again
                return findBuilds($scope,
                    $scope.buildrequest.buildrequestid);
            }
        });

        const data = dataService.open().closeOnDestroy($scope);
        data.getBuildrequests($scope.buildrequestid).onNew = function(buildrequest) {
            $scope.buildrequest = buildrequest;
            data.getBuildsets(buildrequest.buildsetid).onNew = buildset => $scope.buildset = buildset;

            return $scope.builder = buildersService.getBuilder(buildrequest.builderid);
        };
    }
}


angular.module('common')
.directive('buildrequestsummary', ['RecursionHelper', Buildrequestsummary])
.controller('_buildrequestsummaryController', ['$scope', 'dataService', 'buildersService', 'findBuilds', 'resultsService', _buildrequestsummary]);
