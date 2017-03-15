# this file will contains the different generic functions which
# will be called by the different tests
# inspired by this methodology
# http://www.lindstromhenrik.com/using-protractor-with-coffeescript/

class dashboardPage
    constructor: ->

    go: ->
        browser.get('#/mydashboard')

module.exports = dashboardPage
