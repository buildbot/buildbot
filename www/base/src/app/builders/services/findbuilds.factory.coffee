class FindBuilds extends Factory
    constructor: ($log, scopeTimeout, dataService, $state, RESULTS) ->
        find_build = ($scope, buildrequestid, redirect_to_build) ->
            # get the builds that are addressing this buildrequestid
            data = dataService.open($scope)
            data.getBuilds(buildrequestid:buildrequestid).then (builds) ->
                $scope.builds = builds
                found_one_build = false
                for build in builds
                    if build.results != RESULTS.RETRY
                        found_one_build = true
                        if redirect_to_build
                            $state.go "build",
                                builder:build.builderid
                                build:build.number
                            return
                # there is a race condition, if the request is claimed,
                # there might be a slight delay before build is actually visible
                if not found_one_build
                    scopeTimeout $scope, ->
                        find_build($scope, buildrequestid, redirect_to_build)
                    , 1000
        return find_build
