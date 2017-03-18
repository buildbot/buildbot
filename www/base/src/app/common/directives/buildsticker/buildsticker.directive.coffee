class Buildsticker extends Directive('common')
    constructor: (RecursionHelper) ->
        return {
            replace: true
            restrict: 'E'
            scope: {build: '=?', builder: '=?', buildid: '=?'}
            templateUrl: 'views/buildsticker.html'
            controller: '_buildstickerController'
        }
class _buildsticker extends Controller('common')
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
