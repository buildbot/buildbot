class Build extends Controller
    constructor: ($rootScope, $scope, $location, $stateParams, $state,
                  dataService, dataUtilsService, recentStorage, publicFieldsFilter,
                  glBreadcrumbService, glTopbarContextualActionsService, resultsService) ->
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
                $scope.error = "Cannot rebuild: " + why.data.error.message
                refreshContextMenu()

            $scope.build.control('rebuild').then(success, failure)

        doStop = ->
            $scope.is_stopping = true
            refreshContextMenu()

            success = (res) -> null

            failure = (why) ->
                $scope.is_stopping = false
                $scope.error = "Cannot Stop: " + why.data.error.message
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

        data = dataService.open($scope)
        data.getBuilders(builderid).then (builders) ->
            $scope.builder = builder = builders[0]
            builder.getBuilds(number__lt: buildnumber + 2, limit: 3, order: '-number').then (builds) ->
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

                # HACK: we should definitively fix this in the data_module
                # http://trac.buildbot.net/ticket/3380
                build._endpoint = "builds"
                $scope.properties = build.getProperties().getArray()
                $scope.changes = build.getChanges().getArray()
                $scope.$watch 'changes', (changes) ->
                    if changes?
                        responsibles = {}
                        for change in changes
                            change.author_email = dataUtilsService.emailInString(change.author)
                            responsibles[change.author] = change.author_email
                        $scope.responsibles = responsibles
                , true

                data.getBuildslaves(build.buildslaveid).then (buildslaves) ->
                    $scope.buildslave = publicFieldsFilter(buildslaves[0])

                data.getBuildrequests(build.buildrequestid).then (buildrequests) ->
                    $scope.buildrequest = buildrequest = buildrequests[0]
                    data.getBuildsets(buildrequest.buildsetid).then (buildsets) ->
                        $scope.buildset = buildsets[0]
