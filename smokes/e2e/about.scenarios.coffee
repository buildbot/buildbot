# coffee script
# test goal: checks the capability to navigate on about web page
# to use previous and next link

aboutPage = require('./pages/about.coffee')
homePage = require('./pages/home.coffee')
builderPage = require('./pages/builder.coffee')

describe 'about test', () ->
    about = null
    home =  null
    builder = null

    beforeEach () ->
        about = new aboutPage('runtests')
        builder = new builderPage('runtests', 'force')
        home = new homePage()
        home.loginUser("homer@email.com", "doh!")

    afterEach () ->
        home.logOut()

    describe 'check about page', () ->
        it 'should navigate to the about page, check the default elements inside', () ->
            about.goAbout()
            about.checkAboutPage()
            about.checkBuildbotTitle()
            about.checkConfigTitle()
            about.checkDependenciesTitle()
