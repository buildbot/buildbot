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

    it('should go to the home page and check the different builder', async () => {
        const builderName = {
            "0" : "runtests"
        };
        await builder.go();
        await builder.goForce();
        let startButton = force.getStartButton();
        await browser.wait(EC.elementToBeClickable(startButton),
                           5000,
                           "start button not clickable");
        await startButton.click();
        await home.go();
        const panel0 = home.getPanel(0);
        expect(await panel0.getText()).toContain(builderName[0]);
    });
});
