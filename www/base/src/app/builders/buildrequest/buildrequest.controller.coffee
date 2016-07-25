class Buildrequest extends Controller
    constructor: ($scope, dataService, $stateParams, findBuilds, glBreadcrumbService, glTopbarContextualActionsService, publicFieldsFilter) ->
        $scope.is_cancelling = false
        $scope.$watch "buildrequest.claimed", (n, o) ->
            if n  # if it is unclaimed, then claimed, we need to try again
                findBuilds $scope,
                    $scope.buildrequest.buildrequestid,
                    $stateParams.redirect_to_build
                # when a build is discovered, force the tab to go to that build
                savedNew = $scope.builds.onNew
                $scope.builds.onNew = (build) ->
                    build.active = true
                    savedNew(build)

        doCancel = ->
            $scope.is_cancelling = true
            refreshContextMenu()

            success = (res) ->
                # refresh is done via complete event

            failure = (why) ->
                $scope.is_cancelling = false
                $scope.error = "Cannot cancel: " + why.error.message
                refreshContextMenu()

            $scope.buildrequest.control('cancel').then(success, failure)

        refreshContextMenu = ->
            actions = []
            if not $scope.buildrequest?
                return
            if not $scope.buildrequest.complete
                if $scope.is_cancelling
                    actions.push
                       caption: "Cancelling..."
                       icon: "spinner fa-spin"
                       action: doCancel
                else
                    actions.push
                       caption: "Cancel"
                       extra_class: "btn-default"
                       action: doCancel

            glTopbarContextualActionsService.setContextualActions(actions)
        $scope.$watch('buildrequest.complete', refreshContextMenu)

        data = dataService.open().closeOnDestroy($scope)
        data.getBuildrequests($stateParams.buildrequest).onNew = (buildrequest) ->
            $scope.buildrequest = buildrequest
            $scope.raw_buildrequest = publicFieldsFilter(buildrequest)
            data.getBuilders(buildrequest.builderid).onNew = (builder) ->
                $scope.builder = builder
                breadcrumb = [
                        caption: builder.name
                        sref: "builder({builder:#{buildrequest.builderid}})"
                    ,
                        caption: "buildrequests"
                    ,
                        caption: buildrequest.buildrequestid
                        sref: "buildrequest({buildrequest:#{buildrequest.buildrequestid}})"
                ]

                glBreadcrumbService.setBreadcrumb(breadcrumb)

            data.getBuildsets(buildrequest.buildsetid).onNew = (buildset) ->
                $scope.buildset = publicFieldsFilter(buildset)
                buildset.getProperties().onNew  = (properties) ->
                    $scope.properties = publicFieldsFilter(properties)
