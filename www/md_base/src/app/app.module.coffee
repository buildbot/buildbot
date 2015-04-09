angular.module 'app', [
    'ngAria',
    'ngAnimate',
    'ngMaterial',
]
    .config ($mdThemingProvider) ->
        $mdThemingProvider.theme('default')
            .primaryPalette('blue')
            .warnPalette('orange')

    .config ($mdIconProvider) ->
        $mdIconProvider.defaultIconSet('/icons/iconset.svg', 512)

