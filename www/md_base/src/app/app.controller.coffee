class App extends Controller
    name: ''
    view: {}

    openMenu: ->
        @$mdSidenav('left').open()

    constructor: ($scope, $rootScope, @$mdSidenav)->
        $rootScope.$on '$stateChangeSuccess', (event, toState) =>
            @name = toState.name
            @view = toState.data
            @$mdSidenav('left').close() if not @$mdSidenav('left').isLockedOpen()
