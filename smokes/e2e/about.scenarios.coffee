# coffee script
# test goal: checks the capability to navigate on about web page
# to use previous and next link

aboutPage = require('./pages/about.coffee')

describe('', () ->
    about = null

    beforeEach(() ->
        about = new aboutPage('runtests')
    )


    describe 'check about page', () ->
        it 'should navigate to the about page, check the default elements inside', () ->
            about.goAbout()
            about.checkAboutPage()
            about.checkBuildbotTitle()
            about.checkConfigTitle()
            about.checkDependenciesTitle()
)
