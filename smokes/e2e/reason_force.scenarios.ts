// test goal: checks the capability to define a reason and to cancel/start the build

import { HomePage } from './pages/home';
import { ForcePage } from './pages/force';
import { BuilderPage } from './pages/builder';

describe('force and cancel', function() {
    let force = null;
    let builder = null;

    beforeEach(async () => {
        builder = new BuilderPage('runtests', 'force');
        force =  new ForcePage();
        await builder.goDefault();
    });

    afterEach(async () => {
        const homePage = new HomePage();
        await homePage.waitAllBuildsFinished();
    });

    it('should create a build', async () => {
        await builder.go();
        let lastbuild = await builder.getLastSuccessBuildNumber();
        await builder.goForce();
        await force.getStartButton().click();
        await builder.go();
        await builder.waitNextBuildFinished(lastbuild);
    });

    it('should create a build with a dedicated reason and cancel it', async () => {
        await builder.go();
        await builder.goForce();
        await force.getCancelButton().click();
    });

    it('should create a build with a dedicated reason and Start it', async () => {
        await builder.go();
        await builder.goForce();
        await force.setReason("New Test Reason");
        await force.setYourName("FaceLess User");
        await force.setProjectName("BBOT9");
        await force.setBranchName("Gerrit Branch");
        await force.setRepo("http//name.com");
        await force.setRevisionName("12345");
        await force.getStartButton().click();
    });
});
