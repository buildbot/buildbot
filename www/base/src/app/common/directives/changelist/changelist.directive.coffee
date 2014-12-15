class Changelist extends Directive('common')
    constructor: ->
        return {
            replace: true
            restrict: 'E'
            scope: {changes: '='}
            templateUrl: 'views/changelist.html'
            controller: '_changeListController'
        }


class _changeList extends Controller('common')
    constructor: ($scope) ->

        formatAuthor = (change) ->
            # Official W3C email regular expression
            emailRegex = /[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*/
            email = emailRegex.exec(change.author)
            # Remove email from author string
            if email && change.author.split(' ').length > 0
                change.author_name = change.author.replace(///\s<#{email[0]}>///, '')
                change.author_email = email[0]


        $scope.$watch 'changes', (changes) ->
            if changes?
                for change in changes
                    formatAuthor(change)

        $scope.expandDetails = ->
            for change in $scope.changes
                change.show_details = true

        $scope.collapseDetails = ->
            for change in $scope.changes
                change.show_details = false
