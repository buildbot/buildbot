'use strict';
var path = require('path');
var url = require('url');
var yosay = require('yosay');
var yeomanG = require('yeoman-generator');

/* jshint -W106 */

var GeneratorGenerator = module.exports = yeomanG.Base.extend({
  initializing: function () {
    this.pkg = require('../package.json');
    this.currentYear = (new Date()).getFullYear();
    this.config.defaults({'coffee': true});
  },

  prompting: {
    askFor: function () {
      var done = this.async();

      this.log(yosay('Create your own guanlecoja app with superpowers!'));

      var prompts = [{
        name: 'appname',
        message: 'What\'s the base name of your application',
        default: this.appname
      }, {
        name: 'coffee',
        type: 'confirm',
        message: 'Do you want to use coffeescript',
        default: this.config.get('coffee')
      }
    ];

      this.prompt(prompts, function (props) {
        this.appname = props.appname;
        this.coffee = props.coffee;
        this.config.set('coffee', props.coffee);

        done();
      }.bind(this));
    },
  },
  configuring: {
    enforceFolderName: function () {
      if (this.appname !== this._.last(this.destinationRoot().split(path.sep))) {
        this.destinationRoot(this.appname);
      }
      this.config.save();
    }
  },

  writing: {
    projectfiles: function () {
      this.template('_package.json', 'package.json');
      this.template('gulpfile.js', 'gulpfile.js');
      this.template('guanlecoja/config.coffee', 'guanlecoja/config.coffee');
      this.template('README.md');
    },

    gitfiles: function () {
      this.src.copy('gitignore', '.gitignore');
    },

    app: function () {
      this.src.copy('src/styles/styles.less', 'src/styles/styles.less');
      if (this.coffee) {
          this.src.copy('src/app/app.module.coffee', 'src/app/app.module.coffee');
          this.src.copy('src/app/app.spec.coffee', 'src/app/app.spec.coffee');
      } else {
          this.src.copy('src/app/app.module.js', 'src/app/app.module.js');
          this.src.copy('src/app/app.spec.js', 'src/app/app.spec.js');
      }
      this.src.copy('src/app/index.jade', 'src/app/index.jade');
      this.template('src/app/layout.jade', 'src/app/layout.jade');
    },
  },

  end: function () {
    if (!this.options['skip-install']) {
      this.npmInstall();
    }
  }
});
