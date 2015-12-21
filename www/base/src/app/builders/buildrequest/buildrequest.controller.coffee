class Buildrequest extends Controller
    constructor: ($scope, dataService, $stateParams, findBuilds, glBreadcrumbService, glTopbarContextualActionsService, publicFieldsFilter) ->
        $scope.is_cancelling = false
        $scope.$watch "buildrequest.claimed", (n, o) ->
            if n  # if it is unclaimed, then claimed, we need to try again
                findBuilds $scope,
                    $scope.buildrequest.buildrequestid,
                    $stateParams.redirect_to_build

        doCancel = ->
            $scope.is_cancelling = true
            refreshContextMenu()

            success = (res) ->
                $state.go 'builder',
                    builder: $scope.buildrequest.builderid

            failure = (why) ->
                $scope.is_cancelling = false
                $scope.error = "Cannot cancel: " + why.data.error.message
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

        data = dataService.open($scope)
        data.getBuildrequests($stateParams.buildrequest).then (buildrequests) ->
            buildrequest = buildrequests[0]
            $scope.buildrequest = publicFieldsFilter(buildrequest)
            data.getBuilders(buildrequest.builderid).then (builders) ->
                $scope.builder = builder = builders[0]
                breadcrumb = [
                        caption: "buildrequests"
                        sref: "buildrequests"
                    ,
                        caption: builder.name
                        sref: "builder({builder:#{buildrequest.builderid}})"
                    ,
                        caption: buildrequest.buildrequestid
                        sref: "buildrequest({buildrequest:#{buildrequest.buildrequestid}})"
                ]

                glBreadcrumbService.setBreadcrumb(breadcrumb)

            data.getBuildsets(buildrequest.buildsetid).then (buildsets) ->
                $scope.buildset = publicFieldsFilter(buildsets[0])
