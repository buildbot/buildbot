# coffee script
# test goal: checks the capability to navigate in a dedicated build
# to use previous and next link

builderPage = require('./pages/builder.coffee')
waterfallPage = require('./pages/waterfall.coffee')
settingsPage = require('./pages/settings.coffee')

describe('', () ->
    builder = null
    waterfall = null
    settings = null

    beforeEach(() ->
        builder = new builderPage('runtests', 'force')
        waterfall = new waterfallPage('runtests')
        settings =  new settingsPage('runtests')
        builder.goDefault()
    )

    scallingVar = '10'
    describe 'manage settings', () ->
        it 'should navigate to the setting, change the scalling factor and check it', () ->
            settings.goSettings()
            settings.changeScallingFactor(scallingVar)
            waterfall.go()
            settings.goSettings()
            settings.checkScallingFactor(scallingVar)

    columnVar = '450'
    describe 'manage settings', () ->
        it 'should navigate to the settings, change the Column Width and check it', () ->
            settings.goSettings()
            settings.changeColumnWidth(columnVar)
            waterfall.go()
            settings.goSettings()
            settings.checkColumnWidth(columnVar)

    lazyLoadingLimit = '30'
    describe 'manage settings', () ->
        it 'should navigate to the settings, change the Lazy Loading and check it', () ->
            settings.goSettings()
            settings.changeLazyLoadingLimit(lazyLoadingLimit)
            waterfall.go()
            settings.goSettings()
            settings.checkLazyLoadingLimit(lazyLoadingLimit)

    idleTimeVar = '15'
    describe 'manage settings', () ->
        it 'should navigate to the settings, change the Idle Time value and check it', () ->
            settings.goSettings()
            settings.changeIdleTime(idleTimeVar)
            waterfall.go()
            settings.goSettings()
            settings.checkIdleTime(idleTimeVar)

    maxBuildVar = '130'
    describe 'manage settings', () ->
        it 'should navigate to the settings, change the Max Build value and check it', () ->
            settings.goSettings()
            settings.changeMaxBuild(maxBuildVar)
            waterfall.go()
            settings.goSettings()
            settings.checkMaxBuild(maxBuildVar)

    maxBuildersVar='45'
    describe 'manage settings', () ->
        it 'should navigate to the settings, change the Max Builder value and check it', () ->
            settings.goSettings()
            settings.changeMaxRecentsBuilders(maxBuildersVar)
            waterfall.go()
            settings.goSettings()
            settings.checkMaxRecentsBuilders(maxBuildersVar)
)
