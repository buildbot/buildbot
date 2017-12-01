# coffee script
# test goal: checks the capability to define a reason and to cancel/start the build

forcePage = require('./pages/force.coffee')
builderPage = require('./pages/builder.coffee')
homePage = require('./pages/home.coffee')

describe 'force', () ->
    force = null
    builder = null
    home = null

    beforeEach () ->
        builder = new builderPage('runtests', 'force')
        force =  new forcePage()
        home = new homePage()
        home.loginUser("homer@email.com", "doh!")

    afterEach () ->
        new homePage().waitAllBuildsFinished()
        home.logOut()

    lastbuild = null
    it 'should create a build', () ->

        lastbuild = 0
        builder.go()
        builder.getLastSuccessBuildNumber().then (lastbuild) ->
            builder.goForce()
            force.getStartButton().click()
            builder.go()
            builder.waitNextBuildFinished(lastbuild)
