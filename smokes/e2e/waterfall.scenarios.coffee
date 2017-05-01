# coffee script
# test goal: checks the capability to navigate in a dedicated build
# to use previous and next link


forcePage = require('./pages/force.coffee')
builderPage = require('./pages/builder.coffee')
waterfallPage = require('./pages/waterfall.coffee')
homePage = require('./pages/home.coffee')

describe 'waterfall', () ->
    force = null
    builder = null
    waterfall = null

    beforeEach () ->
        builder = new builderPage('runtests', 'force')
        force =  new forcePage()
        waterfall = new waterfallPage('runtests')
        builder.goDefault()

    afterEach () ->
        console.log window.innerHeight, window.innerWidth
        new homePage().waitAllBuildsFinished()

    it 'should navigate to the waterfall, check one builder and hyperlink', () ->
        waterfall.go()
        waterfall.goBuilderAndCheck('runtests')

    it 'should navigate to the builds waterfall and check the associated hyperlink', () ->
        waterfall.go()
        waterfall.goBuildAndCheck()

    it 'should navigate to the builds waterfall and open the popup and close it', () ->
        waterfall.go()
        waterfall.goBuildAndClose()
