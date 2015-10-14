class Buildrequest extends Controller
<<<<<<< Updated upstream
    constructor: ($scope, buildbotService, $stateParams, findBuilds, glBreadcrumbService) ->
=======
    constructor: ($scope, buildbotService, $stateParams, findBuilds, glBreadcrumbService, glTopbarContextualActionsService, $state) ->
        $scope.is_cancelling = false

>>>>>>> Stashed changes
        $scope.$watch "buildrequest.claimed", (n, o) ->
            if n  # if it is unclaimed, then claimed, we need to try again
                findBuilds $scope,
                    $scope.buildrequest.buildrequestid,
                    $stateParams.redirect_to_build

<<<<<<< Updated upstream
=======
        doCancel = ->
            $scope.is_cancelling = true
            refreshContextMenu()

            success = (res) ->
                console.log res

                #$state.go "builders",


            failure = (why) ->
                $scope.is_cancelling = false
                $scope.error = "Cannot Stop: " + why.data.error.message
                refreshContextMenu()

            buildbotService.one("buildrequests", $scope.buildrequest.buildrequestid).control("cancel").then(success, failure)

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

>>>>>>> Stashed changes
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
