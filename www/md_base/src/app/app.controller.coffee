class App extends Controller
    title: ''
    name: ''

    openMenu: ->
        @$mdSidenav('left').open()

    constructor: ($scope, $rootScope, @$mdSidenav)->
        $rootScope.$on '$stateChangeSuccess', (event, toState) =>
            @title = toState.data.title
            @name = toState.name
            @$mdSidenav('left').close() if not @$mdSidenav('left').isLockedOpen()
