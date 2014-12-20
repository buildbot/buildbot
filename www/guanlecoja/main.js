(function() {
  var _, annotate, argv, bower, cached, coffee, concat, connect, cssmin, fixtures2js, fs, gif, gulp_help, gutil, jade, karma, lazypipe, less, lr, ngClassify, path, remember, rename, run_sequence, serveStatic, sourcemaps, templateCache, uglify, vendors, wrap,
    indexOf = [].indexOf || function(item) { for (var i = 0, l = this.length; i < l; i++) { if (i in this && this[i] === item) return i; } return -1; };

  require("./vendors");

  vendors = global.vendors;

  ngClassify = require('gulp-ng-classify');

  path = require('path');

  karma = require('gulp-karma');

  path = vendors.path;

  fs = vendors.fs;

  _ = vendors._;

  argv = vendors.minimist(process.argv.slice(2));

  run_sequence = vendors.run_sequence;

  gif = vendors.gif;

  sourcemaps = vendors.sourcemaps;

  coffee = vendors.coffee;

  gutil = vendors.gutil;

  annotate = vendors.annotate;

  concat = vendors.concat;

  cached = vendors.cached;

  remember = vendors.remember;

  uglify = vendors.uglify;

  jade = vendors.jade;

  wrap = vendors.wrap;

  rename = vendors.rename;

  bower = vendors.bower;

  templateCache = vendors.templateCache;

  lr = vendors.lr;

  cssmin = vendors.cssmin;

  less = vendors.less;

  fixtures2js = vendors.fixtures2js;

  gulp_help = vendors.gulp_help;

  lazypipe = vendors.lazypipe;

  connect = vendors.connect;

  serveStatic = vendors["static"];

  require("coffee-script/register");

  module.exports = function(gulp) {
    var buildConfig, catch_errors, coffeeCompile, config, coverage, defaultHelp, dev, devHelp, jadeCompile, notests, prod, ref, script_sources;
    run_sequence = run_sequence.use(gulp);
    gulp = gulp_help(gulp, {
      afterPrintCallback: function(tasks) {
        console.log(gutil.colors.underline("Options:"));
        console.log(gutil.colors.cyan("  --coverage") + " Runs the test with coverage reports");
        console.log(gutil.colors.cyan("  --notests") + "  Skip running the tests");
        return console.log("");
      }
    });
    prod = indexOf.call(argv._, "prod") >= 0;
    dev = indexOf.call(argv._, "dev") >= 0;
    coverage = argv.coverage;
    notests = argv.notests;
    config = require("./defaultconfig.coffee");
    buildConfig = require(path.join(process.cwd(), "guanlecoja", "config.coffee"));
    _.merge(config, buildConfig);
    if (((ref = buildConfig.karma) != null ? ref.files : void 0) != null) {
      config.karma.files = buildConfig.karma.files;
    }
    if (buildConfig.buildtasks != null) {
      config.buildtasks = buildConfig.buildtasks;
    }
    bower = bower(config.bower);
    bower.installtask(gulp);
    vendors.rimraf.sync(config.dir.build);
    if (coverage) {
      vendors.rimraf.sync(config.dir.coverage);
    }
    if (notests) {
      config.testtasks = ["notests"];
    }
    catch_errors = function(s) {
      s.on("error", function(e) {
        var error;
        error = gutil.colors.bold.red;
        if (e.fileName != null) {
          gutil.log(error(e.plugin + ":" + e.name + ": " + e.fileName + " +" + e.lineNumber));
        } else {
          gutil.log(error(e.plugin + ":" + e.name));
        }
        gutil.log(error(e.message));
        gutil.beep();
        s.end();
        s.emit("end");
        if (!dev) {
          throw e;
        }
        return null;
      });
      return s;
    };
    if (coverage) {
      config.vendors_apart = true;
      config.templates_apart = true;
    }
    script_sources = config.files.app.concat(config.files.scripts);
    if (!config.vendors_apart) {
      script_sources = bower.deps.concat(script_sources);
    }
    if (!config.templates_apart) {
      script_sources = script_sources.concat(config.files.templates);
    }
    if (config.templates_as_js) {
      jadeCompile = lazypipe().pipe(jade, {
        client: true
      }).pipe(rename, {
        extname: ""
      }).pipe(rename, {
        extname: ""
      }).pipe(wrap, "window." + config.templates_global + "['<%= file.relative %>'] = <%= contents %>;").pipe(concat, "templates.js").pipe(wrap, "window." + config.templates_global + "={}; <%= contents %>");
    } else {
      jadeCompile = lazypipe().pipe(jade).pipe(rename, function(p) {
        if ((config.name != null) && config.name !== 'app') {
          p.dirname = path.join(config.name, "views");
        } else {
          p.dirname = "views";
        }
        return p.basename = p.basename.replace(".tpl", "");
      });
    }
    coffeeCompile = lazypipe().pipe(ngClassify, config.ngclassify(config)).pipe(coffee);
    gulp.task('scripts', false, function() {
      if (coverage && config.coffee_coverage) {
        return gulp.src(script_sources).pipe(catch_errors(ngClassify(config.ngclassify(config)))).pipe(gulp.dest(path.join(config.dir.coverage, "src")));
      }
      return gulp.src(script_sources).pipe(gif(dev || config.sourcemaps, sourcemaps.init())).pipe(cached('scripts')).pipe(catch_errors(gif("*.coffee", coffeeCompile()))).pipe(catch_errors(gif("*.jade", jadeCompile()))).pipe(remember('scripts')).pipe(gif("*.html", templateCache({
        module: config.name
      }))).pipe(concat("scripts.js")).pipe(gif(prod, annotate())).pipe(gif(prod, uglify())).pipe(gif(dev || config.sourcemaps, sourcemaps.write("."))).pipe(gulp.dest(config.dir.build)).pipe(gif(dev, lr()));
    });
    gulp.task('vendors', false, function() {
      if (!(config.vendors_apart && bower.deps.length > 0)) {
        return;
      }
      return gulp.src(bower.deps).pipe(gif(dev || config.sourcemaps, sourcemaps.init())).pipe(concat("vendors.js")).pipe(gif(prod, uglify())).pipe(gif(dev || config.sourcemaps, sourcemaps.write("."))).pipe(gulp.dest(config.dir.build)).pipe(gif(dev, lr()));
    });
    gulp.task('templates', false, function() {
      if (!config.templates_apart) {
        return;
      }
      return gulp.src(config.files.templates).pipe(catch_errors(gif("*.jade", jade()))).pipe(gif("*.html", rename(function(p) {
        if ((config.name != null) && config.name !== 'app') {
          p.dirname = path.join(config.name, "views");
        } else {
          p.dirname = "views";
        }
        p.basename = p.basename.replace(".tpl", "");
        return null;
      }))).pipe(gif("*.html", templateCache({
        module: config.name
      }))).pipe(concat("templates.js")).pipe(gulp.dest(config.dir.build));
    });
    gulp.task('tests', false, function() {
      var src;
      src = bower.testdeps.concat(config.files.tests);
      return gulp.src(src).pipe(cached('tests')).pipe(gif(dev, sourcemaps.init())).pipe(catch_errors(gif("*.coffee", ngClassify(config.ngclassify)))).pipe(catch_errors(gif("*.coffee", coffee()))).pipe(remember('tests')).pipe(concat("tests.js")).pipe(gif(dev, sourcemaps.write("."))).pipe(gulp.dest(config.dir.build));
    });
    gulp.task('generatedfixtures', false, config.generatedfixtures);
    gulp.task('fixtures', false, function() {
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
    gulp.task('styles', false, function() {
      return gulp.src(config.files.less).pipe(cached('styles')).pipe(catch_errors(less())).pipe(remember('styles')).pipe(concat("styles.css")).pipe(gif(prod, cssmin())).pipe(gulp.dest(config.dir.build)).pipe(gif(dev, lr()));
    });
    gulp.task('fonts', false, function() {
      return gulp.src(config.files.fonts).pipe(rename({
        dirname: ""
      })).pipe(gulp.dest(path.join(config.dir.build, "fonts")));
    });
    gulp.task('imgs', false, function() {
      return gulp.src(config.files.images).pipe(rename({
        dirname: ""
      })).pipe(gulp.dest(path.join(config.dir.build, "img")));
    });
    gulp.task('index', false, function() {
      return gulp.src(config.files.index).pipe(catch_errors(jade())).pipe(gulp.dest(config.dir.build));
    });
    gulp.task('server', false, ['index'], function(next) {
      var app;
      if (config.devserver != null) {
        app = connect();
        app.use(serveStatic(config.dir.build));
        return app.listen(config.devserver.port);
      } else {
        return next();
      }
    });
    gulp.task("watch", false, function() {
      lr.listen({
        livereload: path.join(__dirname, "livereload.js")
      });
      gulp.watch(script_sources, ["scripts"]);
      gulp.watch(config.files.templates, ["templates"]);
      gulp.watch(config.files.tests, ["tests"]);
      gulp.watch(config.files.less, ["styles"]);
      gulp.watch(config.files.index, ["index"]);
      return null;
    });
    gulp.task("karma", false, function() {
      var classified, i, karmaconf, len, r, ref1, scripts_index;
      karmaconf = {
        basePath: config.dir.build,
        action: dev ? 'watch' : 'run'
      };
      _.merge(karmaconf, config.karma);
      if (config.vendors_apart) {
        karmaconf.files = ["vendors.js"].concat(config.karma.files);
      }
      if (config.templates_apart) {
        karmaconf.files = karmaconf.files.concat(["templates.js"]);
      }
      if (coverage) {
        karmaconf.reporters.push("coverage");
        karmaconf.preprocessors = {
          '**/scripts.js': ['sourcemap', 'coverage'],
          '**/tests.js': ['sourcemap'],
          '**/*.coffee': ['coverage']
        };
        ref1 = karmaconf.coverageReporter.reporters;
        for (i = 0, len = ref1.length; i < len; i++) {
          r = ref1[i];
          if (r.dir === "coverage") {
            r.dir = config.dir.coverage;
          }
        }
        karmaconf.basePath = ".";
        scripts_index = karmaconf.files.indexOf("scripts.js");
        karmaconf.files = karmaconf.files.map(function(p) {
          return path.join(config.dir.build, p);
        });
        if (config.coffee_coverage) {
          classified = script_sources.map(function(p) {
            return path.join("coverage", p);
          });
          karmaconf.files.splice.apply(karmaconf.files, [scripts_index, 1].concat(classified));
        }
      }
      return gulp.src(karmaconf.files).pipe(karma(karmaconf));
    });
    gulp.task("notests", false, function() {
      return null;
    });
    defaultHelp = "Build and test the code once, without minification";
    if (argv.help || argv.h) {
      gulp.task("default", defaultHelp, ['help'], function() {});
    } else {
      gulp.task("default", defaultHelp, function(callback) {
        return run_sequence(config.preparetasks, config.buildtasks, config.testtasks, callback);
      });
    }
    devHelp = "Run needed tasks for development: build, tests, watch and rebuild. This task only ends when you hit CTRL-C!";
    if (config.devserver) {
      devHelp += "\nAlso runs the dev server";
    }
    gulp.task("dev", devHelp, ['default', 'watch', "server"]);
    return gulp.task("prod", "Run production build (minified)", ['default']);
  };

}).call(this);
