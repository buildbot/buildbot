// test goal: checks the capability to define a reason and to cancel/start the build

import { ForcePage } from './pages/force';
import { BuilderPage } from './pages/builder';
import { HomePage } from './pages/home';

describe('force', function() {
    let force = null;
    let builder = null;

    beforeEach(function() {
        builder = new BuilderPage('runtests', 'force');
        force =  new ForcePage();
        return builder.goDefault();
    });
    afterEach(() => new HomePage().waitAllBuildsFinished());

    let lastbuild = null;
    it('should create a build', function() {

        lastbuild = 0;
        builder.go();
        builder.getLastSuccessBuildNumber().then(function(lastbuild) {
            builder.goForce();
            force.getStartButton().click();
            builder.go();
            builder.waitNextBuildFinished(lastbuild);
        });
    });
});
