class Changelist extends Directive('common')
    constructor: ->
        return {
            replace: true
            restrict: 'E'
            scope: {changes: '=?'}
            templateUrl: 'views/changelist.html'
            controller: '_changeListController'
        }

class _changeList extends Controller('common')
    constructor: ($scope, dataUtilsService) ->

        $scope.expandDetails = ->
            for change in $scope.changes
                change.show_details = true

        $scope.collapseDetails = ->
            for change in $scope.changes
                change.show_details = false
