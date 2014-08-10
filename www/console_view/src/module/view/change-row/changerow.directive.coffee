angular.module('buildbot.console_view').directive 'changeRow',
    [ ->
        replace: false
        restrict: 'EA' # E: Element, A: Attribute
        scope: {
            width: '='
            cellWidth: '='
            change: '='
        }
        templateUrl: 'buildbot.console_view/views/changerow.html'
        controller: ['$scope', 'resultsService', '$modal', class
            constructor: ($scope, resultsService, @$modal) ->
                angular.extend @, resultsService

                $scope.$on 'showAllInfo', (event, value) =>
                    @infoIsCollapsed = value

                $scope.$watch 'width', (@width) =>
                $scope.$watch 'cellWidth', (@cellWidth) =>
                $scope.$watch 'change', (@change) =>
                    if @change
                        if angular.isString(@change.author)
                            @_formatAuthor()
                        if angular.isString(@change.repository)
                            @_createLink()

            infoIsCollapsed: true

            _formatAuthor: ->
                # Official W3C email regular expression
                emailRegex = /[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*/
                email = emailRegex.exec(@change.author)
                # Remove email from author string
                if email && @change.author.split(' ').length > 0
                    @change.author = @change.author.replace(///\s<#{email[0]}>///, '')
                    @change.email = email[0]

            _createLink: ->
                repository = @change.repository.replace('.git', '')
                @change.link = "#{repository}/commit/#{@change.revision}"

            selectBuild: (build) ->
                modal = @$modal.open
                    templateUrl: 'buildbot.console_view/views/modal.html'
                    controller: 'modalController as modal'
                    windowClass: 'modal-small'
                    resolve:
                        selectedBuild: -> build

            createFileLink: (file) ->
                repository = @change.repository.replace('.git', '')
                return "#{repository}/blob/#{@change.revision}/#{file}"

            toggleInfo: ->
                @infoIsCollapsed = !@infoIsCollapsed
        ]
        controllerAs: 'cr'
    ]
