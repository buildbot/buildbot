class Buildsticker extends Directive('common')
    constructor: (RecursionHelper) ->
        return {
            replace: true
            restrict: 'E'
            scope: {build: '='}
            templateUrl: 'views/buildsticker.html'
            controller: '_buildstickerController'
        }

class _buildsticker extends Controller('common')
    constructor: ($scope, dataService, resultsService, $urlMatcherFactory, $location) ->
        $scope.$watch (-> moment().unix()), ->
            $scope.now = moment().unix()

        # make resultsService utilities available in the template
        _.mixin($scope, resultsService)

        data = dataService.open($scope)
        $scope.$watch 'build', (build) ->
            data.getBuilders(build.builderid).then (builders) ->
                $scope.builder = builders[0]
