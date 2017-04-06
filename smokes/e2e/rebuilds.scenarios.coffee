# coffee script
# test goal: checks the capability to navigate in a dedicated build
# to use previous and next link


homePage = require('./pages/home.coffee')
forcePage = require('./pages/force.coffee')
builderPage = require('./pages/builder.coffee')

describe 'rebuilds', () ->
    force = null
    builder = null
    home = null

    beforeEach () ->
        builder = new builderPage('runtests', 'force')
        force =  new forcePage()
        home = new homePage()
        home.loginUser("homer@email.com", "doh!")

    afterEach () ->
        home.logOut()

    xit 'should navigate to a dedicated build and to use the rebuild button', () ->
        builder.go()
        builder.getLastSuccessBuildNumber().then (lastbuild) ->
            builder.goForce()
            force.getStartButton().click()
            builder.go()
            builder.waitNextBuildFinished(lastbuild)
            builder.goBuild(lastbuild)
            browser.getCurrentUrl().then (buildUrl) ->
                browser.sleep(4000)
                builder.getRebuildButton().click()
                builder.waitGoToBuild(lastbuild+2)
