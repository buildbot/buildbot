(function() {
  var annotate, argv, bower, cached, coffee, concat, connect, cssmin, fixtures2js, fs, gif, gutil, jade, karma, less, lr, ngClassify, path, remember, rename, run_sequence, serve_static, sourcemaps, templateCache, uglify, _,
    __indexOf = [].indexOf || function(item) { for (var i = 0, l = this.length; i < l; i++) { if (i in this && this[i] === item) return i; } return -1; };

  run_sequence = require('run-sequence');

  require("coffee-script/register");

  path = require('path');

  fs = require('fs');

  _ = require('lodash');

  argv = require('minimist')(process.argv.slice(2));

  ngClassify = require('gulp-ng-classify');

  gif = require('gulp-if');

  sourcemaps = require('gulp-sourcemaps');

  coffee = require('gulp-coffee');

  gutil = require('gulp-util');

  annotate = require('gulp-ng-annotate');

  concat = require('gulp-concat');

  cached = require('gulp-cached');

  karma = require('gulp-karma');

  remember = require('gulp-remember');

  uglify = require('gulp-uglify');

  jade = require('gulp-jade');

  rename = require('gulp-rename');

  bower = require('gulp-bower-deps');

  templateCache = require('./gulp-angular-templatecache');

  lr = require('gulp-livereload');

  cssmin = require('gulp-minify-css');

  less = require('gulp-less');

  fixtures2js = require('gulp-fixtures2js');

  connect = require('connect');

  serve_static = require("serve-static");

  module.exports = function(gulp) {
    var buildConfig, config, dev, error_handler, prod, script_sources;
    prod = __indexOf.call(argv._, "prod") >= 0;
    dev = __indexOf.call(argv._, "dev") >= 0;
    config = require("./defaultconfig.coffee");
    buildConfig = require(path.join(process.cwd(), "guanlecoja", "config.coffee"));
    _.merge(config, buildConfig);
    bower = bower(config.bower);
    bower.installtask(gulp);
    require('rimraf').sync(config.dir.build);
    error_handler = function(e) {
      var error;
      error = gutil.colors.bold.red;
      if (e.fileName != null) {
        gutil.log(error("" + e.plugin + ":" + e.name + ": " + e.fileName + " +" + e.lineNumber));
      } else {
        gutil.log(error("" + e.plugin + ":" + e.name));
      }
      gutil.log(error(e.message));
      gutil.beep();
      this.end();
      this.emit("end");
      if (!dev) {
        throw e;
      }
    };
    script_sources = bower.deps.concat(config.files.app, config.files.scripts, config.files.templates);
    gulp.task('scripts', function() {
      return gulp.src(script_sources).pipe(gif(dev || config.sourcemaps, sourcemaps.init())).pipe(cached('scripts')).pipe(gif("*.coffee", ngClassify(config.ngclassify(config)).on('error', error_handler))).pipe(gif("*.coffee", coffee().on('error', error_handler))).pipe(gif("*.jade", jade().on('error', error_handler))).pipe(gif("*.html", rename(function(p) {
        if (config.name != null) {
          p.dirname = path.join(config.name, "views");
        } else {
          p.dirname = "views";
        }
        p.basename = p.basename.replace(".tpl", "");
        return null;
      }))).pipe(remember('scripts')).pipe(gif("*.html", templateCache({
        module: config.name
      }))).pipe(concat("scripts.js")).pipe(gif(prod, annotate())).pipe(gif(prod, uglify())).pipe(gif(dev || config.sourcemaps, sourcemaps.write("."))).pipe(gulp.dest(config.dir.build)).pipe(gif(dev, lr()));
    });
    gulp.task('tests', function() {
      var src;
      src = bower.testdeps.concat(config.files.tests);
      return gulp.src(src).pipe(cached('tests')).pipe(gif(dev, sourcemaps.init())).pipe(gif("*.coffee", ngClassify(config.ngclassify))).pipe(gif("*.coffee", coffee().on('error', error_handler))).pipe(remember('tests')).pipe(concat("tests.js")).pipe(gif(dev, sourcemaps.write("."))).pipe(gulp.dest(config.dir.build));
    });
    gulp.task('generatedfixtures', config.generatedfixtures);
    gulp.task('fixtures', function() {
      return gulp.src(config.files.fixtures, {
        base: process.cwd()
      }).pipe(rename({
        dirname: ""
      })).pipe(fixtures2js("fixtures.js", {
        postProcessors: {
          "**/*.json": "json"
        }
      })).pipe(gulp.dest(config.dir.build));
    });
    gulp.task('styles', function() {
      return gulp.src(config.files.less).pipe(cached('styles')).pipe(less().on('error', error_handler)).pipe(remember('styles')).pipe(concat("styles.css")).pipe(gif(prod, cssmin())).pipe(gulp.dest(config.dir.build)).pipe(gif(dev, lr()));
    });
    gulp.task('fonts', function() {
      return gulp.src(config.files.fonts).pipe(rename({
        dirname: ""
      })).pipe(gulp.dest(path.join(config.dir.build, "fonts")));
    });
    gulp.task('imgs', function() {
      return gulp.src(config.files.images).pipe(rename({
        dirname: ""
      })).pipe(gulp.dest(path.join(config.dir.build, "img")));
    });
    gulp.task('index', function() {
      return gulp.src(config.files.index).pipe(jade().on('error', error_handler)).pipe(gulp.dest(config.dir.build));
    });
    gulp.task('server', ['index'], function(next) {
      if (config.devserver != null) {
        return connect().use(serve_static(config.dir.build)).listen(config.devserver.port, next);
      } else {
        return next();
      }
    });
    gulp.task("watch", function() {
      gulp.watch(script_sources, ["scripts"]);
      gulp.watch(config.files.tests, ["tests"]);
      gulp.watch(config.files.less, ["styles"]);
      gulp.watch(config.files.index, ["index"]);
      return null;
    });
    gulp.task("karma", function() {
      var karmaconf;
      karmaconf = {
        basePath: config.dir.build,
        action: dev ? 'watch' : 'run'
      };
      _.merge(karmaconf, config.karma);
      return gulp.src(["scripts.js", 'generatedfixtures.js', "fixtures.js", "tests.js"]).pipe(karma(karmaconf));
    });
    gulp.task("default", function(callback) {
      return run_sequence(config.preparetasks, config.buildtasks, config.testtasks, callback);
    });
    gulp.task("dev", ['default', 'watch', "server"]);
    return gulp.task("prod", ['default']);
  };

}).call(this);
