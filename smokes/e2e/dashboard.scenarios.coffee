# coffee script
# test goal: checks the the number of element present in home page
# to test this part: two different builds need to be started


forcePage = require('./pages/force.coffee')
builderPage = require('./pages/builder.coffee')
dashboardPage = require('./pages/dashboard.coffee')
homePage = require('./pages/home.coffee')


describe 'dashboard page', () ->
    force = null
    builder = null
    home = null
    dashboard = null

    beforeEach () ->
        builder = new builderPage('runtests', 'force')
        force =  new forcePage()
        dashboard = new dashboardPage()
        home = new homePage()
        builder.goDefault()

    afterEach (done) ->
        browser.manage().logs().get('browser').then (browserLog) ->
            console.log browserLog
            expect(browserLog.length).toEqual(0)
            done()

    it 'should go to the dashboard page and see no error', () ->
        builder.goForce()
        force.getStartButton().click()
        home.waitAllBuildsFinished()
        dashboard.go()
