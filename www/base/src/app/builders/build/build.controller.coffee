class Build extends Controller
    constructor: ($rootScope, $scope, $location, buildbotService, $stateParams, recentStorage, glBreadcrumbService, glTopbarContextualActionsService,
                $state) ->

        builderid = _.parseInt($stateParams.builder)
        buildnumber = _.parseInt($stateParams.build)

        $scope.last_build = true
        $scope.is_stopping = false

        $scope.$watch 'build.complete', (n, o) ->
            if n == true
                glTopbarContextualActionsService.setContextualActions []

            else if n == false and not $scope.is_stopping
                glTopbarContextualActionsService.setContextualActions [
                        caption: "Stop"
                        extra_class: "btn-danger"
                        action: ->
                            $scope.is_stopping = true
                            buildbotService.one("builds", $scope.build.buildid).control("stop")
                ]

        $scope.$watch 'is_stopping', (n, o) ->
            if n == true
                glTopbarContextualActionsService.setContextualActions [
                        caption: "Stopping..."
                        icon: "spinner"
                        extra_class: "spin"
                ]

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
