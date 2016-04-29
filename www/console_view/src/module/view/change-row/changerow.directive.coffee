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

        $scope.$watch 'width', (@width) =>
        $scope.$watch 'cellWidth', (@cellWidth) =>
        $scope.$watch 'change', (@change) =>
            if @change
                if angular.isString(@change.repository)
                    @createLink()

    createLink: ->
        repository = @change.repository.replace('.git', '')
        @change.link = "#{repository}/commit/#{@change.revision}"

    selectBuild: (build) ->
        modal = @$uibModal.open
            templateUrl: 'console_view/views/modal.html'
            controller: 'consoleModalController as modal'
            windowClass: 'modal-small'
            resolve:
                selectedBuild: -> build

    createFileLink: (file) ->
        repository = @change.repository.replace('.git', '')
        return "#{repository}/blob/#{@change.revision}/#{file}"

    toggleInfo: ->
        @infoIsCollapsed = !@infoIsCollapsed
