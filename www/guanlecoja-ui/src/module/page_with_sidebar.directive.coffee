class GlPageWithSidebar extends Directive
    constructor: ->
        return {
            replace: true
            transclude: true
            restrict: 'E'
            scope: false
            controllerAs: "c"
            templateUrl: "guanlecoja.ui/views/page_with_sidebar.html"
            controller: "glPageWithSidebarCController"
        }

class GlPageWithSidebarC extends Controller
    constructor: ($scope) ->
        $scope.groups = [
            caption: "foo"
            sref: "foo"
            icon: 'bomb'
            items: [
                caption: "foofoo"
                sref: "foofoo"
            ,
                caption: "foobar"
                sref: "foobar"
            ]
        ,
            caption: "bar"
            sref: "bar"
            icon: 'bank'
            items: [
                caption: "barfoo"
                sref: "barfoo"
            ,
                caption: "barbar"
                sref: "barbar"
            ]
        ]

        console.log $scope
