class Home extends Controller
    title: ''
    titleURL: ''

    constructor: ($scope, config, @bbSettingsService) ->
        @title = config.title
        @titleURL = config.titleURL

        @settings = @bbSettingsService.getSettingsGroup("home")

        @sortable_settings =
            disabled: @settings.lock_panels.value
            animation: 150
            handle: '.title'

        @panels = @settings.panels.value

        @editing_panels = !@settings.lock_panels.value

        $scope.$watch 'home.panels', (=> @bbSettingsService.save()), true

    edit_panels: (state) ->
        @editing_panels = state
        @sortable_settings.disabled = !state
        @settings.lock_panels.value = !state
        @bbSettingsService.save()
