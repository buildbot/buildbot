class Home extends Controller
    title: ''
    titleURL: ''

    constructor: ($scope, config, bbSettingsService) ->
        @title = config.title
        @titleURL = config.titleURL

        @settings = bbSettingsService.getSettingsGroup("home")

        @sortable_settings =
            disabled: @settings.lock_panels.value
            animation: 150
            handle: '.title'

        @panels = @settings.panels.value

        $scope.$watch 'home.panels', (-> bbSettingsService.save()), true
        $scope.$watch 'home.settings.lock_panels', (-> bbSettingsService.save()), true
