// test goal: checks the the number of element present in home page
// to test this part: two different builds need to be started


const forcePage = require('./pages/force.js');
const builderPage = require('./pages/builder.js');
const dashboardPage = require('./pages/dashboard.js');
const homePage = require('./pages/home.js');


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

    it('should go to the dashboard page and see no error', function() {
        builder.goForce();
        force.getStartButton().click();
        home.waitAllBuildsFinished();
        dashboard.go();
    });
});
