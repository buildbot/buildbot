import { browser, by, element, ExpectedConditions as EC } from 'protractor';
import { post } from 'request';
import { ConsolePage } from './pages/console';
import { BuilderPage } from './pages/builder';
import { HomePage } from './pages/home';
import { testPageUrl } from './pages/base';

describe('change hook', function() {
    let builder = null;
    beforeEach(function() {
        builder = new BuilderPage('runtests1', 'force');
    });

    afterEach(async () => {
        const homePage = new HomePage();
        await homePage.waitAllBuildsFinished();
    });

    it('should create a build', async () => {
        await builder.go();
        let lastbuild = await builder.getLastFinishedBuildNumber();
        await post(`${testPageUrl}/change_hook/base`).form({
            comments:'sd',
            project:'pyflakes',
            repository:'https://github.com/buildbot/hello-world.git',
            author:'foo <foo@bar.com>',
            committer:'foo <foo@bar.com>',
            revision: 'HEAD',
            branch:'master'
        });
        await builder.waitBuildFinished(lastbuild + 1);
        let result = await builder.getBuildResult(lastbuild + 1);
        expect(result).toEqual("SUCCESS");
    });
});
