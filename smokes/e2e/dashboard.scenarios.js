/*
 * decaffeinate suggestions:
 * DS102: Remove unnecessary code created because of implicit returns
 * Full docs: https://github.com/decaffeinate/decaffeinate/blob/master/docs/suggestions.md
 */
// coffee script
// test goal: checks the the number of element present in home page
// to test this part: two different builds need to be started


const forcePage = require('./pages/force.coffee');
const builderPage = require('./pages/builder.coffee');
const dashboardPage = require('./pages/dashboard.coffee');
const homePage = require('./pages/home.coffee');


describe('dashboard page', function() {
    let force = null;
    let builder = null;
    let home = null;
    let dashboard = null;

    beforeEach(function() {
        builder = new builderPage('runtests', 'force');
        force =  new forcePage();
        dashboard = new dashboardPage();
        home = new homePage();
        return builder.goDefault();
    });

    afterEach(done =>
        browser.manage().logs().get('browser').then(function(browserLog) {
            console.log(browserLog);
            expect(browserLog.length).toEqual(0);
            return done();
        })
    );

    return it('should go to the dashboard page and see no error', function() {
        builder.goForce();
        force.getStartButton().click();
        home.waitAllBuildsFinished();
        return dashboard.go();
    });
});
