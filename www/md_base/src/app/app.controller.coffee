class App extends Controller
    current: ''
    navitems: [
        {
            name: 'home'
            title: 'home'
            icon: 'home'
        },
        {
            name: 'builds'
            title: 'builds'
            icon: 'gear'
        },
        {
            name: 'settings'
            title: 'settings'
            icon: 'toggle'
        }
        {
            name: 'about'
            title: 'about'
            icon: 'info'
        }
    ]
    constructor: ($scope, $rootScope)->
        $rootScope.$on '$stateChangeSuccess', (event, toState) =>
            @current = toState.name
