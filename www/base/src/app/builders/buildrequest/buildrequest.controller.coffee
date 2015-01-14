class Buildrequest extends Controller
    constructor: ($scope, buildbotService, $stateParams, findBuilds, glBreadcrumbService) ->
        $scope.$watch "buildrequest.claimed", (n, o) ->
            if n  # if it is unclaimed, then claimed, we need to try again
                findBuilds $scope,
                    $scope.buildrequest.buildrequestid,
                    $stateParams.redirect_to_build

        buildbotService.bindHierarchy($scope, $stateParams, ['buildrequests'])
        .then ([buildrequest]) ->
            buildbotService.one("builders", buildrequest.builderid).bind($scope).then (builder) ->
                breadcrumb = [
                        caption: "buildrequests"
                        sref: "buildrequests"
                    ,
                        caption: builder.name
                        sref: "builder({builder:#{buildrequest.builderid}})"
                    ,
                        caption: buildrequest.id
                        sref: "buildrequest({buildrequest:#{buildrequest.id}})"
                ]

                glBreadcrumbService.setBreadcrumb(breadcrumb)
            buildbotService.one("buildsets", buildrequest.buildsetid).bind($scope)
