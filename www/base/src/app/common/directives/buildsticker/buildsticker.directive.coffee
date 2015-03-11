class Buildsticker extends Directive('common')
    constructor: (RecursionHelper) ->
        return {
            replace: true
            restrict: 'E'
            scope: {build: '='}
            templateUrl: 'views/buildsticker.html'
            compile: RecursionHelper.compile
            controller: '_buildstickerController'
        }

class _buildsticker extends Controller('common')
    constructor: ($scope, buildbotService, resultsService, $urlMatcherFactory, $location) ->
        $scope.$watch (-> moment().unix()), ->
            $scope.now = moment().unix()

        # make resultsService utilities available in the template
        _.mixin($scope, resultsService)

        $scope.$watch 'build', (build) ->
            buildbotService.one('builders', build.builderid).bind($scope)
