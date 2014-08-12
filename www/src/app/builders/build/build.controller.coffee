class Build extends Controller
    constructor: ($rootScope, $scope, $location, buildbotService, $stateParams, recentStorage) ->

        buildbotService.bindHierarchy($scope, $stateParams, ['builders', 'builds'])
        .then ([builder, build]) ->
            $rootScope.$broadcast "breadcrumb", [
                    caption: "Builders"
                    sref: "builders"
                ,
                    caption: builder.name
                    sref: "builder({builder:#{builder.id}})"
                ,
                    caption: build.number
                    sref: "build({build:#{build.number}})"
            ]
            buildbotService.one("buildslaves", build.buildslaveid).bind($scope)
            buildbotService.one("buildrequests", build.buildrequestid)
            .bind($scope).then (buildrequest) ->
                buildset = buildbotService.one("buildsets", buildrequest.buildsetid)
                buildset.bind($scope)
                buildset.one("properties").bind($scope, dest_key:'properties')
                recentStorage.addBuild
                    link: "#/builders/#{$scope.builder.builderid}/build/#{$scope.build.number}"
                    caption: "#{$scope.builder.name} / #{$scope.build.number}"
