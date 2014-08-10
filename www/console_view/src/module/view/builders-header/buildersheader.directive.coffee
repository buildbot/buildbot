class BuildersHeader extends Directive('console_view')
    constructor: ->
        return {
            replace: true
            restrict: 'EA' # E: Element, A: Attribute
            scope: {
                width: '='
                cellWidth: '='
                builders: '='
            }
            templateUrl: 'console_view/views/buildersheader.html'
            controller: '_buildersHeaderController'
            controllerAs: 'bh'
        }

class _buildersHeader extends Controller('console_view')
    constructor: ($scope) ->
        $scope.$watch 'width', (@width) =>
        $scope.$watch 'cellWidth', (@cellWidth) =>
        $scope.$watchCollection 'builders', (@builders) =>