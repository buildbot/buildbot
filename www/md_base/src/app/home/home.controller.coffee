class Home extends Controller
    title: ''
    titleURL: ''
    constructor: ($scope, config, bbSettingsService) ->
        @title = config.title
        @titleURL = config.titleURL

        @settings = bbSettingsService.getSettingsGroup("home")
        $scope.$watch 'home.settings',(-> bbSettingsService.save()), true
