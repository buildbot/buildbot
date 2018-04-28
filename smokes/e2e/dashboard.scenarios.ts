// test goal: checks the the number of element present in home page
// to test this part: two different builds need to be started


import { ForcePage } from './pages/force';
import { BuilderPage } from './pages/builder';
import { DashboardPage } from './pages/dashboard';
import { HomePage } from './pages/home';


describe('dashboard page', function() {
    let force = null;
    let builder = null;
    let home = null;
    let dashboard = null;

    beforeEach(function() {
        builder = new BuilderPage('runtests', 'force');
        force =  new ForcePage();
        dashboard = new DashboardPage();
        home = new HomePage();
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
