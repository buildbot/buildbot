class Buildsticker
    constructor: (RecursionHelper) ->
        return {
            replace: true
            restrict: 'E'
            scope: {build: '=?', builder: '=?', buildid: '=?'}
            templateUrl: 'views/buildsticker.html'
            controller: '_buildstickerController'
        }
class _buildsticker
    constructor: ($scope, dataService, buildersService, resultsService, $urlMatcherFactory, $location) ->
        $scope.$watch (-> moment().unix()), ->
            $scope.now = moment().unix()

        # make resultsService utilities available in the template
        _.mixin($scope, resultsService)

        data = dataService.open().closeOnDestroy($scope)
        $scope.$watch "buildid", (buildid) ->
            if not buildid? then return
            data.getBuilds(buildid).onNew = (build) ->
                $scope.build = build

        $scope.$watch 'build', (build) ->
            if not $scope.builder and build?.builderid?
                $scope.builder = buildersService.getBuilder(build.builderid)


angular.module('common')
.directive('buildsticker', ['RecursionHelper', Buildsticker])
.controller('_buildstickerController', ['$scope', 'dataService', 'buildersService', 'resultsService', '$urlMatcherFactory', '$location', _buildsticker])