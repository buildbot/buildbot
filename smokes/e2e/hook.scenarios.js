/*
 * decaffeinate suggestions:
 * DS102: Remove unnecessary code created because of implicit returns
 * Full docs: https://github.com/decaffeinate/decaffeinate/blob/master/docs/suggestions.md
 */
const consolePage = require('./pages/console.coffee');
const builderPage = require('./pages/builder.coffee');
const homePage = require('./pages/home.coffee');

describe('change hook', function() {
    let builder = null;
    let console = null;
    beforeEach(function() {
        builder = new builderPage('runtests1', 'force');
        return console = new consolePage();
    });
    afterEach(() => new homePage().waitAllBuildsFinished());

    return it('should create a build', function() {
        builder.go();
        builder.getLastSuccessBuildNumber().then(function(lastbuild) {
            browser.executeAsyncScript(done=>
                $.post('change_hook/base', {
                    comments:'sd',
                    project:'pyflakes',
                    repository:'git://github.com/buildbot/hello-world.git',
                    author:'foo <foo@bar.com>',
                    revision: 'HEAD',
                    branch:'master'
                    }, done)
            );
            return builder.waitNextBuildFinished(lastbuild);
        });
        console.go();
        return expect(console.countSuccess()).toBeGreaterThan(0);
    });
});
