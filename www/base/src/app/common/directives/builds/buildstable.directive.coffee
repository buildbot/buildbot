class BuildsTable extends Directive('common')
    constructor: (RecursionHelper) ->
        return {
            replace: true
            restrict: 'E'
            scope: {builds: '=?', builder: '=?', builders: '=?'}
            templateUrl: 'views/buildstable.html'
            controller: '_buildstableController'
        }
class _buildstable extends Controller('common')
    constructor: ($scope, resultsService) ->
        # make resultsService utilities available in the template
        _.mixin($scope, resultsService)
        return
