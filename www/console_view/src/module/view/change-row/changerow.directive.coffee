class ChangeRow extends Directive
    constructor: ->
        return {
            replace: false
            restrict: 'EA' # E: Element, A: Attribute
            scope: {
                width: '='
                cellWidth: '='
                change: '='
            }
            templateUrl: 'console_view/views/changerow.html'
            controller: '_changeRowController'
            controllerAs: 'cr'
        }

class _changeRow extends Controller
    constructor: ($scope, resultsService, @$modal) ->
        angular.extend @, resultsService
        @infoIsCollapsed = true

        $scope.$on 'showAllInfo', (event, value) =>
            @infoIsCollapsed = value

        $scope.$watch 'width', (@width) =>
        $scope.$watch 'cellWidth', (@cellWidth) =>
        $scope.$watch 'change', (@change) =>
            if @change
                if angular.isString(@change.author)
                    @formatAuthor()
                if angular.isString(@change.repository)
                    @createLink()

    formatAuthor: ->
        # Official W3C email regular expression
        emailRegex = /[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*/
        email = emailRegex.exec(@change.author)
        # Remove email from author string
        if email && @change.author.split(' ').length > 0
            @change.author = @change.author.replace(///\s<#{email[0]}>///, '')
            @change.email = email[0]

    createLink: ->
        repository = @change.repository.replace('.git', '')
        @change.link = "#{repository}/commit/#{@change.revision}"

    selectBuild: (build) ->
        modal = @$modal.open
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