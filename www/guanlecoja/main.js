(function() {
  var __indexOf = [].indexOf || function(item) { for (var i = 0, l = this.length; i < l; i++) { if (i in this && this[i] === item) return i; } return -1; };

  module.exports = function(gulp) {
    var annotate, argv, buildConfig, cached, coffee, concat, config, cssmin, dev, fixtures2js, fs, gif, gutil, jade, karma, less, lr, ngClassify, path, prod, remember, rename, script_sources, sourcemaps, templateCache, uglify, _;
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
    templateCache = require('gulp-angular-templatecache');
    lr = require('gulp-livereload');
    cssmin = require('gulp-minify-css');
    less = require('gulp-less');
    fixtures2js = require('gulp-fixtures2js');
    prod = __indexOf.call(argv._, "prod") >= 0;
    dev = __indexOf.call(argv._, "dev") >= 0;
    config = require("./defaultconfig.coffee");
    buildConfig = require(path.join(process.cwd(), "guanlecoja", "config.coffee"));
    _.merge(config, buildConfig);
    require('rimraf').sync(config.dir.build);
    script_sources = config.files.library.js.concat(config.files.app, config.files.scripts, config.files.templates);
    gulp.task('scripts', function() {
      return gulp.src(script_sources).pipe(cached('scripts')).pipe(gif(dev, sourcemaps.init())).pipe(gif("*.coffee", ngClassify())).on('error', gutil.log).pipe(gif("*.coffee", coffee())).on('error', gutil.log).pipe(gif("*.jade", jade())).on('error', gutil.log).pipe(gif("*.html", rename(function(p) {
        p.dirname = "views";
        p.basename = p.basename.replace(".tpl", "");
        return null;
      }))).pipe(gif("*.html", templateCache({
        module: "app"
      }))).pipe(remember('scripts')).pipe(concat("scripts.js")).pipe(gif(prod, annotate())).pipe(gif(prod, uglify())).pipe(gif(dev, sourcemaps.write("."))).pipe(gulp.dest(config.dir.build)).pipe(gif(dev, lr()));
    });
    gulp.task('tests', function() {
      var src;
      src = config.files.library.tests.concat(config.files.tests);
      return gulp.src(src).pipe(cached('tests')).pipe(gif(dev, sourcemaps.init())).pipe(gif("*.coffee", ngClassify())).pipe(gif("*.coffee", coffee())).on('error', gutil.log).pipe(remember('tests')).pipe(concat("tests.js")).pipe(gif(dev, sourcemaps.write("."))).pipe(gulp.dest(config.dir.build));
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
      return gulp.src(config.files.less).pipe(cached('styles')).pipe(less()).pipe(remember('styles')).pipe(concat("styles.css")).pipe(gif(prod, cssmin())).pipe(gulp.dest(config.dir.build)).pipe(gif(dev, lr()));
    });
    gulp.task('fonts', function() {
      return gulp.src(config.files.fonts).pipe(gulp.dest(config.dir.build + "/fonts"));
    });
    gulp.task('imgs', function() {
      return gulp.src(config.files.images).pipe(gulp.dest(config.dir.build + "/img"));
    });
    gulp.task('index', function() {
      return gulp.src(config.files.index).pipe(jade()).pipe(gulp.dest(config.dir.build));
    });
    gulp.task("watch", function() {
      gulp.watch(script_sources, ["scripts"]);
      gulp.watch(config.files.tests, ["tests"]);
      gulp.watch(config.files.less, ["styles"]);
      return null;
    });
    gulp.task("default", ['scripts', 'styles', 'fonts', 'imgs', 'index', 'tests', 'generatedfixtures', 'fixtures'], function() {
      var karmaconf;
      karmaconf = {
        basePath: config.dir.build,
        action: dev ? 'watch' : 'run'
      };
      _.merge(karmaconf, config.karma);
      return gulp.src(["scripts.js", 'generatedfixtures.js', "fixtures.js", "tests.js"]).pipe(karma(karmaconf));
    });
    gulp.task("dev", ['default', 'watch']);
    return gulp.task("prod", ['default']);
  };

}).call(this);
