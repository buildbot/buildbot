# This file is part of Buildbot.  Buildbot is free software: you can
# redistribute it and/or modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation, version 2.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51
# Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Copyright Buildbot Team Members

import sys
import os, shutil
import urllib2
import zipfile
import platform
from twisted.internet import defer, threads
from buildbot.util import in_reactor

js_deps = [("http://download.dojotoolkit.org/release-1.8.1/dojo-release-1.8.1-src.zip",
            "dojo-release-1.8.1-src/", "."),
           ("https://github.com/kriszyp/xstyle/archive/v0.0.5.zip",
            "xstyle-0.0.5/","xstyle"),
           ("https://github.com/kriszyp/put-selector/archive/v0.3.2.zip",
            "put-selector-0.3.2/","put-selector"),
           ("https://github.com/SitePen/dgrid/archive/v0.3.3.zip",
            "dgrid-0.3.3/","dgrid"),
           ("https://github.com/timrwood/moment/archive/1.7.2.zip","moment-1.7.2/min/moment.min.js","moment.js")
           ]
def syncStatic(config,www, workdir, olddir):
    """Synchronize the static directory"""
    if not config['quiet']:
        print "copying the javascript UI to base directory %s" % (config['basedir'],)
    source_dir = os.path.join(os.path.dirname(__file__), "..","www","static")
    extra_js = www.get('extra_js', [])
    if os.path.exists(workdir):
        shutil.rmtree(workdir)
    if os.path.exists(olddir):
        shutil.rmtree(olddir)
    if not config['develop'] or platform.system() == "Windows":
        shutil.copytree(source_dir, workdir)
        for d in extra_js:
            if os.path.exists(d) and os.path.isdir(d):
                shutil.copytree(d, os.path.join(workdir, "js", os.path.basename(d)))
    else:
        os.mkdir(workdir)
        for d in "img css".split():
            os.symlink(os.path.join(source_dir, d), os.path.join(workdir, d))
        os.mkdir(os.path.join(workdir, "js"))
        for f in os.listdir(os.path.join(source_dir,"js")):
            os.symlink(os.path.join(source_dir, "js", f), os.path.join(workdir, "js",f))
        for d in extra_js:
            if os.path.exists(d) and os.path.isdir(d):
                os.symlink(d, os.path.join(workdir, "js", os.path.basename(d)))

def downloadJSDeps(config, workdir):
    if not config['quiet']:
        print "Downloading JS dependancies %s" % (config['basedir'],)
    depsdir = os.path.join(config['basedir'], ".jsdeps_tarballs")
    if not os.path.isdir(depsdir):
        os.mkdir(depsdir)
    for url, archivedir, archivedest in js_deps:
        fn = os.path.join(depsdir, os.path.basename(url))
        if not os.path.exists(fn):
            f = urllib2.urlopen(url)
            o = open(fn, "wb")
            total_size = int(f.info().getheader('Content-Length').strip())
            chunk_size = 1024*1024
            bytes_so_far = 0
            while True:
                if not config['quiet']:
                    print "Downloading %s: %d%%" % (url,100*bytes_so_far/total_size)
                chunk = f.read(chunk_size)
                bytes_so_far += len(chunk)
                if not chunk:
                    break
                o.write(chunk)
            o.close()
        z = zipfile.ZipFile(fn)
        for member in z.infolist():
            if not member.filename.startswith(archivedir):
                continue
            isdir =  member.external_attr & 16
            dest = os.path.join(workdir, "js", archivedest)
            if member.filename[len(archivedir):]:
                dest = os.path.join(dest, member.filename[len(archivedir):])
            if isdir:
                if not os.path.exists(dest):
                    os.makedirs(dest)
            else:
                if not config['quiet']:
                    print "extracting %s" % (member.filename)
                o = open(dest,"wb")
                o.write(z.read(member))
                o.close()
build_js = """
dependencies = (function(){
    var _packages = "dojox dijit put-selector lib dgrid xstyle moment %(extra_pkg)s".split(" ");
    var packages = [];
    for (var i = 0;i<_packages.length; i+=1) {
	if (_packages[i].length >1) {
	    packages.push([ _packages[i], "../"+_packages[i]]);
	    }
        }
    return {
        basePath: "%(basePath)s",
        releaseDir: "%(releaseDir)s",
        prefixes:packages,
        layers: [
		{
			name: "dojo.js",
			customBase: true,
			dependencies: [
			    "dojo/_base/declare",
			]
		},
		{
			name: "../lib/router.js",
			dependencies: [
				"lib.router"
			]
		}
        ]
    };
}());
console.log(JSON.stringify(dependencies,null, " "))
"""
def minifyJS(config, www, workdir):
    skip_minify = False
    if config['develop']:
        skip_minify = True

    elif os.system("java -version"):
        print "you need a working version of java for dojo build system to work"
        skip_minify = True

    elif platform.system() != "Windows" and os.system("node -v"):
        print "you need a working version of node.js in your path for dojo build system to work"
        skip_minify = True

    # Todo: need to find out the best way to distribute minified code in buildbot's sdist.
    # we'll sort this out once we have more code and requirements for the whole sdist picture
    # Perhaps its even only needed for large scale buildbot where we can require installation of
    # node and java in the master, and where people dont care about sdists.
    if skip_minify:
        # link js to js.built, so that the non minified code is used
        os.symlink("js", os.path.join(workdir, "js.built"))
        return True

    # create the build.js config file that dojo build system is needing
    o = open(os.path.join(workdir,"js","build.js"), "w")
    extra_js = www.get('extra_js', [])
    o.write(build_js% dict(extra_pkg=" ".join([os.path.basename(js) for js in extra_js]),
                           basePath = os.path.join(workdir,"js"),
                           releaseDir = os.path.join(workdir,"jsrelease")))
    o.close()
    os.chdir(os.path.join(workdir,"js"))

    # Those scripts are part of the dojo tarball that we previously downloaded
    if not config['quiet']:
        print "optimizing the javascript UI for better performance in %s" % (config['basedir'],)
    if platform.system() == "Windows":
        os.system("util/buildscripts/build.bat --bin java -p build.js --release")
    else:
        os.system("sh util/buildscripts/build.sh --bin node -p build.js --release")
    os.rename(os.path.join(workdir,"jsrelease", "dojo"),os.path.join(workdir,"js.built"))
    shutil.rmtree(os.path.join(workdir,"jsrelease"))

    return True

def updateJS(config, master_cfg=None):
    if 'skip_updatejs' in config:
        return 0
    if not master_cfg:
        from upgrade_master import loadConfig # avoid recursive import
        master_cfg = loadConfig(config)
    if not master_cfg:
        www = {}
    else:
        www = master_cfg.www
    workdir = os.path.join(config['basedir'], "public_html", "static.new")
    olddir = os.path.join(config['basedir'], "public_html", "static.old")
    static = os.path.join(config['basedir'], "public_html", "static")
    syncStatic(config, www, workdir, olddir)
    downloadJSDeps(config, workdir)
    if not minifyJS(config, www, workdir):
        return 1
    if os.path.exists(static):
        os.rename(static, olddir)
    os.rename(workdir, static)
    if not config['quiet']:
        print "javascript UI configured in %s" % (config['basedir'],)

    return 0
