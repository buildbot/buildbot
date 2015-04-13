class App extends Controller
    title: ''
    constructor: ($scope, $rootScope)->
        $rootScope.$on '$stateChangeSuccess', (event, toState) =>
            @title = toState.name
