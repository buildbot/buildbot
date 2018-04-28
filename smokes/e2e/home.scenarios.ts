// test goal: checks the the number of element present in home page
// to test this part: two different builds need to be started

import { ForcePage } from './pages/force';
import { BuilderPage } from './pages/builder';
import { HomePage } from './pages/home';

describe('home page', function() {
    let force = null;
    let builder = null;
    let home = null;

    beforeEach(function() {
        builder = new BuilderPage('runtests', 'force');
        force =  new ForcePage();
        home = new HomePage();
        return home.loginUser("my@email.com", "mypass");
    });

    afterEach(() => home.logOut());

    it('should go to the home page and check the different builder', function() {
        const builderName = {
            "0" : "runtests"
        };
        builder.go();
        builder.goForce();
        force.getStartButton().click();
        home.go();
        const panel0 = home.getPanel(0);
        expect(panel0.getText()).toContain(builderName[0]);
    });
});
