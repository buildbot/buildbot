class Builder extends Controller
    constructor: ($rootScope, $scope, dataService, $stateParams, resultsService, recentStorage,
        glBreadcrumbService, $state, glTopbarContextualActionsService, $q, $window) ->
        # make resultsService utilities available in the template
        _.mixin($scope, resultsService)
        data = dataService.open().closeOnDestroy($scope)
        builderid = $stateParams.builder
        $scope.forceschedulers = []
        $scope.is_cancelling = false

        data.getBuilders(builderid).onNew = (builder) ->
            $window.document.title = $state.current.data.pageTitle
                builder: builder['name']
            $scope.builder = builder
            breadcrumb = [
                    caption: "Builders"
                    sref: "builders"
                ,
                    caption: builder.name
                    sref: "builder({builder:#{builder.builderid}})"
            ]
            recentStorage.addBuilder
                link: "#/builders/#{builder.builderid}"
                caption: builder.name

            # reinstall breadcrumb when coming back from forcesched
            $scope.$on '$stateChangeSuccess', ->
                glBreadcrumbService.setBreadcrumb(breadcrumb)
            glBreadcrumbService.setBreadcrumb(breadcrumb)

            doCancel = ->
                if $scope.is_cancelling
                    return
                if not window.confirm("Are you sure you want to cancel all builds?")
                    return
                $scope.is_cancelling = true
                refreshContextMenu()

                success = (res) ->
                    $scope.is_cancelling = false
                    refreshContextMenu()

                failure = (why) ->
                    $scope.is_cancelling = false
                    $scope.error = "Cannot cancel: " + why.error.message
                    refreshContextMenu()

                dl = []
                $scope.buildrequests.forEach (buildrequest) ->
                    if not buildrequest.claimed
                        dl.push buildrequest.control('cancel')
                $scope.builds.forEach (build) ->
                    if not build.complete
                        dl.push build.control('stop')
                $q.when(dl).then(success, failure)

            refreshContextMenu = ->
                if $scope.$$destroyed
                    return
                actions = [
                ]
                canStop = false
                $scope.builds.forEach (build) ->
                    if not build.complete
                        canStop = true
                $scope.buildrequests.forEach (buildrequest) ->
                    if not buildrequest.claimed
                        canStop = true

                if canStop
                    if $scope.is_cancelling
                        actions.push
                            caption: "Cancelling..."
                            icon: "spinner fa-spin"
                            action: doCancel
                    else
                        actions.push
                            caption: "Cancel whole queue"
                            extra_class: "btn-danger"
                            icon: "stop"
                            action: doCancel
                _.forEach $scope.forceschedulers, (sch) ->
                    actions.push
                        caption: sch.button_name
                        extra_class: "btn-primary"
                        action: ->
                            $state.go("builder.forcebuilder",
                                scheduler:sch.name)

                glTopbarContextualActionsService.setContextualActions(actions)

            builder.getForceschedulers().onChange = (forceschedulers) ->
                $scope.forceschedulers = forceschedulers
                refreshContextMenu()
                # reinstall contextual actions when coming back from forcesched
                $scope.$on '$stateChangeSuccess', ->
                    refreshContextMenu()
            $scope.numbuilds = 200
            if $stateParams.numbuilds?
                $scope.numbuilds = +$stateParams.numbuilds
            $scope.builds = builder.getBuilds
                property: ["owner", "workername"]
                limit: $scope.numbuilds
                order: '-number'
            $scope.buildrequests = builder.getBuildrequests(claimed:false)
            $scope.builds.onChange=refreshContextMenu
            $scope.buildrequests.onChange=refreshContextMenu
