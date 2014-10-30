class Build extends Controller
    constructor: ($rootScope, $scope, $location, buildbotService, $stateParams, recentStorage, glBreadcrumbService, $state) ->
        builderid = _.parseInt($stateParams.builder)
        buildnumber = _.parseInt($stateParams.build)

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
            if buildnumber > 1
                breadcrumb.splice 0,0,
                    caption: '←'
                    sref: "build({build:#{buildnumber - 1}})"

            glBreadcrumbService.setBreadcrumb(breadcrumb)
            buildbotService.one('builders', builderid).one('builds', buildnumber + 1).bind($scope, dest_key:"nextbuild")

            $scope.$watch 'nextbuild.number', (n, o) ->
                if not o? and n?
                    breadcrumb.push
                        caption: '→'
                        sref: "build({build:#{buildnumber + 1}})"
                    glBreadcrumbService.setBreadcrumb(breadcrumb)

            buildbotService.one("buildslaves", build.buildslaveid).bind($scope)
            buildbotService.one("buildrequests", build.buildrequestid)
            .bind($scope).then (buildrequest) ->
                buildset = buildbotService.one("buildsets", buildrequest.buildsetid)
                buildset.bind($scope)
                buildset.one("properties").bind($scope, dest_key:'properties')
                recentStorage.addBuild
                    link: "#/builders/#{$scope.builder.builderid}/build/#{$scope.build.number}"
                    caption: "#{$scope.builder.name} / #{$scope.build.number}"
