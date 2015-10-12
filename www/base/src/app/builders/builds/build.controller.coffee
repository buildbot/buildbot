class Build extends Controller
    constructor: ($rootScope, $scope, $location, buildbotService, $stateParams,
                  recentStorage, glBreadcrumbService, glTopbarContextualActionsService,
                  $state) ->

        builderid = _.parseInt($stateParams.builder)
        buildnumber = _.parseInt($stateParams.build)

        $scope.last_build = true
        $scope.is_stopping = false
        $scope.is_rebuilding = false

        doRebuild = ->
            $scope.is_rebuilding = true

            success = (res) ->
                refreshContextMenu()
                brid = _.values(res.result[1])[0]
                $state.go "buildrequest",
                    buildrequest: brid
                    redirect_to_build: true

            failure = (why) ->
                $scope.error = "Cannot rebuild: " + why.data.error.message
                refreshContextMenu()

            buildbotService.one("builds", $scope.build.buildid).control("rebuild").then(success, failure)

        doStop = ->
            $scope.is_stopping = true

            success = (res) ->
                refreshContextMenu()

            failure = (why) ->
                $scope.error = "Cannot Stop: " + why.data.error.message
                refreshContextMenu()

            buildbotService.one("builds", $scope.build.buildid).control("stop").then(success, failure)

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

        buildbotService.bindHierarchy($scope, $stateParams, ['builders', 'builds'])
        .then ([builder, build]) ->
            if not build.number? and buildnumber > 1
                $state.go('build', builder:builderid, build:buildnumber - 1)
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

            buildbotService.one('builders', builderid).one('builds', buildnumber + 1).bind($scope, dest_key:"nextbuild")
            buildbotService.one('builds', build.id).all('changes').bind($scope)
            $scope.$watch "changes", (changes) ->
                if changes?
                    responsibles = {}
                    for change in changes
                        responsibles[change.author] = change.author_email
                    $scope.responsibles = responsibles
            , true
            buildbotService.one("buildslaves", build.buildslaveid).bind($scope)
            buildbotService.one("builds", build.id).all("properties").bind($scope)
            buildbotService.one("buildrequests", build.buildrequestid)
            .bind($scope).then (buildrequest) ->
                buildbotService.one("buildsets", buildrequest.buildsetid).bind($scope)
                recentStorage.addBuild
                    link: "#/builders/#{$scope.builder.builderid}/builds/#{$scope.build.number}"
                    caption: "#{$scope.builder.name} / #{$scope.build.number}"
