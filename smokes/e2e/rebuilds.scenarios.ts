// test goal: checks the capability to navigate in a dedicated build
// to use previous and next link


import { HomePage } from './pages/home';
import { ForcePage } from './pages/force';
import { BuilderPage } from './pages/builder';

describe('rebuilds', function() {
    let force = null;
    let builder = null;

    beforeEach(function() {
        builder = new BuilderPage('runtests', 'force');
        force =  new ForcePage();
        return builder.goDefault();
    });

    afterEach(() => new HomePage().waitAllBuildsFinished());

    it('should navigate to a dedicated build and to use the rebuild button', function() {
        builder.go();
        return builder.getLastSuccessBuildNumber().then(function(lastbuild) {
            builder.goForce();
            force.getStartButton().click();
            builder.go();
            builder.waitNextBuildFinished(lastbuild);
            builder.goBuild(lastbuild);
            browser.getCurrentUrl().then(function(buildUrl) {
                builder.getRebuildButton().click();
                builder.waitGoToBuild(lastbuild+2);
            });
        });
    });
});
