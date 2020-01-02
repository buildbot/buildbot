// test goal: checks the the number of element present in home page
// to test this part: two different builds need to be started

import { ForcePage } from './pages/force';
import { BuilderPage } from './pages/builder';
import { HomePage } from './pages/home';
import { browser, by, element, ExpectedConditions as EC } from 'protractor';

describe('home page', function() {
    let force = null;
    let builder = null;
    let home = null;

    beforeEach(async () => {
        builder = new BuilderPage('runtests', 'force');
        force =  new ForcePage();
        home = new HomePage();
        await home.loginUser("my@email.com", "mypass");
    });

    afterEach(async () => await home.logOut());

    it('should go to the home page and check if panel with builder name exists', async () => {
        const builderName = {
            "0" : "runtests"
        };
        await builder.go();
        const buildnumber = await builder.getLastFinishedBuildNumber();
        await builder.goForce();
        await force.clickStartButtonAndWaitRedirectToBuild();
        await builder.go();
        await builder.waitBuildFinished(buildnumber + 1);
        await home.go();
        const panel0 = home.getPanel().first();
        expect(await panel0.getText()).toContain(builderName[0]);
    });
});
