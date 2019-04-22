module.exports =
    # gulp plugins
    run_sequence: require 'run-sequence'
    minimist: require('minimist')
    path: require('path')
    fs: require('fs')
    gif: require 'gulp-if'
    babel: require 'gulp-babel'
    sourcemaps: require 'gulp-sourcemaps'
    annotate: require 'gulp-ng-annotate'
    concat: require 'gulp-concat'
    cached: require 'gulp-cached'
    remember: require 'gulp-remember'
    uglify: require('gulp-uglify-es').default
    jade: require 'gulp-pug'
    wrap: require 'gulp-wrap'
    rename: require 'gulp-rename'
    connect: require 'connect'
    static: require 'serve-static'
    bower: require 'gulp-bower-deps'
    rimraf: require 'rimraf'
    templateCache: require 'gulp-angular-templatecache'
    lr: require 'gulp-livereload'
    cssmin: require 'gulp-clean-css'
    less: require 'gulp-less'
    fixtures2js: require 'gulp-fixtures2js'
    gulp_help: require 'gulp-help'
    lazypipe: require 'lazypipe'

    _: require('lodash')
    coffee: require 'gulp-coffee'
    gutil: require 'gulp-util'

global.vendors = module.exports
