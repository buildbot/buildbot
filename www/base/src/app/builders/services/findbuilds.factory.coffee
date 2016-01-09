class FindBuilds extends Factory
    constructor: ($log, scopeTimeout, dataService, $state, RESULTS) ->
        find_build = ($scope, buildrequestid, redirect_to_build) ->
            # get the builds that are addressing this buildrequestid
            data = dataService.open().closeOnDestroy($scope)
            $scope.builds = data.getBuilds(buildrequestid:buildrequestid)
            $scope.builds.onNew  = (build) ->
                if build.results != RESULTS.RETRY
                    if redirect_to_build
                        $state.go "build",
                            builder:build.builderid
                            build:build.number
                        return

                    # we found a candidate build, no need to keep registered to the stream of builds
                    $scope.builds.close()
        return find_build
