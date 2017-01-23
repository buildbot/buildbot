class Build extends Controller
    constructor: ($rootScope, $scope, $location, $stateParams, $state,
                  dataService, dataUtilsService, recentStorage, publicFieldsFilter,
                  glBreadcrumbService, glTopbarContextualActionsService, resultsService, $window) ->
        _.mixin($scope, resultsService)

        builderid = _.parseInt($stateParams.builder)
        buildnumber = _.parseInt($stateParams.build)

        $scope.last_build = true
        $scope.is_stopping = false
        $scope.is_rebuilding = false

        doRebuild = ->
            $scope.is_rebuilding = true
            refreshContextMenu()
            success = (res) ->
                brid = _.values(res.result[1])[0]
                $state.go "buildrequest",
                    buildrequest: brid
                    redirect_to_build: true

            failure = (why) ->
                $scope.is_rebuilding = false
                $scope.error = "Cannot rebuild: " + why.error.message
                refreshContextMenu()

            $scope.build.control('rebuild').then(success, failure)

        doStop = ->
            $scope.is_stopping = true
            refreshContextMenu()

            success = (res) -> null

            failure = (why) ->
                $scope.is_stopping = false
                $scope.error = "Cannot Stop: " + why.error.message
                refreshContextMenu()

            $scope.build.control('stop').then(success, failure)

        refreshContextMenu = ->
            actions = []
            if not $scope.build?
                return
            if $scope.build.complete
                if $scope.is_rebuilding
                    actions.push
                        caption: "Rebuilding..."
                        icon: "spinner fa-spin"
                        action: doRebuild
                else
                    actions.push
                        caption: "Rebuild"
                        extra_class: "btn-default"
                        action: doRebuild
            else
                if $scope.is_stopping
                    actions.push
                        caption: "Stopping..."
                        icon: "spinner fa-spin"
                        action: doStop
                else
                    actions.push
                        caption: "Stop"
                        extra_class: "btn-default"
                        action: doStop
            glTopbarContextualActionsService.setContextualActions(actions)
        $scope.$watch('build.complete', refreshContextMenu)

        data = dataService.open().closeOnDestroy($scope)
        data.getBuilders(builderid).onChange = (builders) ->
            $scope.builder = builder = builders[0]
            $window.document.title = $state.current.data.pageTitle
                builder: builder['name'], build: buildnumber

            # get the build plus the previous and next
            # note that this registers to the updates for all the builds for that builder
            # need to see how that scales
            builder.getBuilds(number__lt: buildnumber + 2, limit: 3, order: '-number').onChange = (builds) ->
                $scope.prevbuild = null
                $scope.nextbuild = null
                build = null
                for b in builds
                    if b.number == buildnumber - 1
                        $scope.prevbuild = b
                    if b.number == buildnumber
                        $scope.build = build = b
                    if b.number == buildnumber + 1
                        $scope.nextbuild = b
                        $scope.last_build = false

                if not build
                    $state.go('build', builder: builderid, build: builds[0].number)
                    return

                breadcrumb = [
                        caption: "Builders"
                        sref: "builders"
                    ,
                        caption: builder.name
                        sref: "builder({builder:#{builderid}})"
                    ,
                        caption: build.number
                        sref: "build({build:#{buildnumber}})"
                ]

                glBreadcrumbService.setBreadcrumb(breadcrumb)

                unwatch = $scope.$watch 'nextbuild.number', (n, o) ->
                    if n?
                        $scope.last_build = false
                        unwatch()

                recentStorage.addBuild
                    link: "#/builders/#{$scope.builder.builderid}/builds/#{$scope.build.number}"
                    caption: "#{$scope.builder.name} / #{$scope.build.number}"

                build.getProperties().onNew = (properties) ->
                    $scope.properties = properties
                $scope.changes = build.getChanges()
                $scope.responsibles = {}
                $scope.changes.onNew = (change) ->
                    $scope.responsibles[change.author_name] = change.author_email

                data.getWorkers(build.workerid).onNew = (worker) ->
                    $scope.worker = publicFieldsFilter(worker)

                data.getBuildrequests(build.buildrequestid).onNew = (buildrequest) ->
                    $scope.buildrequest = buildrequest
                    data.getBuildsets(buildrequest.buildsetid).onNew = (buildset) ->
                        $scope.buildset = buildset
                        if buildset.parent_buildid
                            data.getBuilds(buildset.parent_buildid).onNew = (build) ->
                                $scope.parent_build = build
