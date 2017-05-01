# this file will contains the different generic functions which
# will be called by the different tests
# inspired by this methodology
# http://www.lindstromhenrik.com/using-protractor-with-coffeescript/

BasePage = require("./base.coffee")

class AboutPage extends BasePage
    constructor: (builder) ->
        @builder = builder

    goAbout: () ->
        browser.get('#/about')

    checkAboutPage: () ->
        expect(browser.getCurrentUrl()).toContain('#/about')

    checkBuildbotTitle: () ->
        aboutTitle = element.all(By.css('h2')).first()
        expect(aboutTitle.getText()).toContain('About this')
        expect(aboutTitle.getText()).toContain('buildbot')

    checkConfigTitle: () ->
        configurationTitle = element.all(By.css('h2')).get(1)
        expect(configurationTitle.getText()).toContain('Configuration')

    checkDependenciesTitle: () ->
        dependenciesTitle = element.all(By.css('h2')).get(2)
        expect(dependenciesTitle.getText()).toContain('Javascript dependencies')

module.exports = AboutPage
