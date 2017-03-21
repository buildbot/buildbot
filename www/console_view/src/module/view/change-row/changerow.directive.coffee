class ChangeRow extends Directive
    constructor: ->
        return {
            replace: false
            restrict: 'EA' # E: Element, A: Attribute
            scope: {
                width: '='
                cellWidth: '='
                change: '=?'
            }
            templateUrl: 'console_view/views/changerow.html'
            controller: '_changeRowController'
            controllerAs: 'cr'
        }


class _changeRow extends Controller
    constructor: ($scope, resultsService, @$uibModal) ->
        angular.extend this, resultsService
        @infoIsCollapsed = true

        $scope.$on 'showAllInfo', (event, value) =>
            @infoIsCollapsed = value


    selectBuild: (build) ->
        modal = @$uibModal.open
            templateUrl: 'console_view/views/modal.html'
            controller: 'consoleModalController as modal'
            windowClass: 'modal-small'
            resolve:
                selectedBuild: -> build

    toggleInfo: ->
        @infoIsCollapsed = !@infoIsCollapsed
