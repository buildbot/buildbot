/*
 * decaffeinate suggestions:
 * DS102: Remove unnecessary code created because of implicit returns
 * Full docs: https://github.com/decaffeinate/decaffeinate/blob/master/docs/suggestions.md
 */
class FindBuilds {
    constructor($log, scopeTimeout, dataService, $state, RESULTS) {
        const find_build = function($scope, buildrequestid, redirect_to_build) {
            // get the builds that are addressing this buildrequestid
            const data = dataService.open().closeOnDestroy($scope);
            $scope.builds = data.getBuilds({buildrequestid});
            $scope.builds.onNew  = function(build) {
                if (build.results !== RESULTS.RETRY) {
                    if (redirect_to_build) {
                        $state.go("build", {
                            builder:build.builderid,
                            build:build.number
                        }
                        );
                        return;
                    }

                    // we found a candidate build, no need to keep registered to the stream of builds
                    $scope.builds.close();
                }
            };
        };
        return find_build;
    }
}


angular.module('app')
.factory('findBuilds', ['$log', 'scopeTimeout', 'dataService', '$state', 'RESULTS', FindBuilds]);
