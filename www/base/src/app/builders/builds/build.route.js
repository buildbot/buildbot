class BuildState {
    constructor($stateProvider, bbSettingsServiceProvider) {

        // Name of the state
        const name = 'build';

        // Register new state
        const state = {
            controller: `${name}Controller`,
            template: require('./build.tpl.jade'),
            name,
            url: '/builders/:builder/builds/:build',
            data: {
                pageTitle: _.template("Buildbot: builder <%= builder %> build <%= build %>")
            }
        };

        $stateProvider.state(state);
        bbSettingsServiceProvider.addSettingsGroup({
            name:'LogPreview',
            caption: 'LogPreview related settings',
            items:[{
                type:'integer',
                name:'loadlines',
                caption:'Initial number of lines to load',
                default_value: 40
            }
            , {
                type:'integer',
                name:'maxlines',
                caption:'Maximum number of lines to show',
                default_value: 40
            }
            , {
                type:'text',
                name:'expand_logs',
                caption:'Expand logs with these names (use ; as separator)',
                default_value: 'summary'
            }
            ]});
    }
}


angular.module('app')
.config(['$stateProvider', 'bbSettingsServiceProvider', BuildState]);
