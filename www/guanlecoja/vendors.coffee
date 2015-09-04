module.exports =
    # gulp plugins
    run_sequence: require 'run-sequence'
    minimist: require('minimist')
    path: require('path')
    fs: require('fs')
    gif: require 'gulp-if'
    sourcemaps: require 'gulp-sourcemaps'
    annotate: require 'gulp-ng-annotate'
    concat: require 'gulp-concat'
    cached: require 'gulp-cached'
    remember: require 'gulp-remember'
    uglify: require 'gulp-uglify'
    jade: require 'gulp-jade'
    wrap: require 'gulp-wrap'
    rename: require 'gulp-rename'
    connect: require 'connect'
    static: require 'serve-static'
    bower: require 'gulp-bower-deps'
    rimraf: require 'rimraf'
    templateCache: require 'gulp-angular-templatecache'
    lr: require 'gulp-livereload'
    cssmin: require 'gulp-minify-css'
    less: require 'gulp-less'
    fixtures2js: require 'gulp-fixtures2js'
    gulp_help: require 'gulp-help'
    lazypipe: require 'lazypipe'
    karma: require 'gulp-karma'

    _: require('lodash')
    coffee: require 'gulp-coffee'
    gutil: require 'gulp-util'

global.vendors = module.exports
