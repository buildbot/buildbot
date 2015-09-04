'use strict';

var gulp = require('gulp'),
coffee = require('gulp-coffee'),
browserify = require('gulp-browserify'),
rename = require('gulp-rename'),
gutil = require('gulp-util'),
uglify = require('gulp-uglify'),
replace = require('gulp-replace');

gulp.task('scripts', function(){
	return gulp.src('main.coffee')
	.pipe(coffee()).on('error', gutil.log)
	.pipe(gulp.dest('.'));
});

gulp.task('vendors', function(){
	return gulp.src('vendors.coffee',  { read: false })
    .pipe(browserify({
      transform: ['coffeeify'],
      extensions: ['.coffee'],
	  builtins: false,
	  commondir: false,
	  detectGlobals: false,
	  insertGlobals : false,
      // those packages need to access files from the package
	  // readline is required in a deadcode path
	  // body-parser use dynamic parsing of its source code
	  // consolidate requires tons of template package deps and is a dep of gulp-wrap > 0.8, and thus gulp-wrap should not be upgraded
	  exclude: ['karma', 'readline', 'body-parser'],
      ignore: ['./lib-cov/connect'],
	}))
	.on('error', gutil.log)
	/* hack in order to have bower browserified */
	/* bower tried to open ../package.json to find out its version */
	.pipe(replace(/var pkg = require\(path/, 'var pkg = {version:"1"}; //'))
    .pipe(rename('vendors.js'))
    .pipe(uglify())
	.pipe(gulp.dest('.'));
});

gulp.task('watch', function()
{
	return gulp.watch('main.coffee', ['scripts']);
});
gulp.task('watch2', function()
{
	return gulp.watch('vendors.coffee', ['vendors']);
});
gulp.task('default', ['scripts', 'vendors', 'watch', 'watch2']);
