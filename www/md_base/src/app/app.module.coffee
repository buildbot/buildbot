angular.module 'app', [
    'ngAria',
    'ngAnimate',
    'ngMaterial',
    'bbData'
    'ui.router',
    'ng-sortable',
    'angularMoment',
]
    .config ($mdThemingProvider) ->
        $mdThemingProvider.theme('default')
            .primaryPalette('deep-purple')
            .warnPalette('orange')

    .config ($mdIconProvider) ->
        $mdIconProvider.defaultIconSet('/icons/iconset.svg', 512)
