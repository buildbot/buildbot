class Buildsticker extends Directive('common')
    constructor: (RecursionHelper) ->
        return {
            replace: true
            restrict: 'E'
            scope: {build: '=', builder:'='}
            templateUrl: 'views/buildsticker.html'
            controller: '_buildstickerController'
        }
class _buildsticker extends Controller('common')
    constructor: ($scope, dataService, resultsService, $urlMatcherFactory, $location) ->
        $scope.$watch (-> moment().unix()), ->
            $scope.now = moment().unix()

        # make resultsService utilities available in the template
        _.mixin($scope, resultsService)

        data = dataService.open().closeOnDestroy($scope)
        $scope.$watch 'build', (build) ->
            if not $scope.builder?
                data.getBuilders(build.builderid).then (builders) ->
                    $scope.builder = builders[0]
