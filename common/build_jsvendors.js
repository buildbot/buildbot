const Q = require("q");
let fs = require("fs");
let path = require("path");
const glob = require("glob");
const Logger = require("bower-logger");
const Project = require("bower/lib/core/Project");
const { Tracker } = require("bower/lib/util/analytics");
const defaultConfig = require("bower/lib/config");
const exec = require("shelljs").exec;
require("coffeescript/register");
fs = require("fs");
path = require("path");
const mout = require("mout");

const pkg = path.resolve(process.argv[2]);
const guanlecoja_opts = require(path.join(pkg, "guanlecoja", "config.coffee"));
const deps_spec = guanlecoja_opts.bower.deps;
const test_deps_spec = guanlecoja_opts.bower.testdeps;
const opts = {};
opts.directory = "libs";
opts.cwd = pkg;
opts.deps = deps_spec;
const dir = "libs";
/* included in the frontend */
const summaryfile = path.join("libs", "bowerdeps.js");
/* potencially read by the distro */
const metadatafile = path.join("libs", "bowerdeps.json");
process.chdir(pkg);

// generate bowerjson automatically
const bowerjson = {
  name: "foo",
  dependencies: {}
};
const to_add_file_list = [];

function process_deps(deps) {
  if (deps == null) {
    return [];
  }
  let file_list = [];
  console.log(deps);
  for (let name in deps) {
    const spec = deps[name];
    if (!Array.isArray(spec.files)) {
      spec.files = [spec.files];
    }
    if (typeof spec.additional_files === "undefined") {
      spec.additional_files = [];
    } else if (!Array.isArray(spec.additional_files)) {
      spec.additional_files = [spec.additional_files];
    }
    for (let file of Array.from(spec.files)) {
      file = path.join(dir, name, file);
      file_list.push(file);
      to_add_file_list.push(file);
    }
    for (let file of Array.from(spec.additional_files)) {
      file = path.join(dir, name, file);
      to_add_file_list.push(file);
    }
    bowerjson.dependencies[name] = spec.version;
  }
  return file_list;
}
const file_list = process_deps(deps_spec);
process_deps(test_deps_spec);
file_list.push(summaryfile);
to_add_file_list.push(summaryfile);
to_add_file_list.push(metadatafile);
if (opts.interactive == null) {
  opts.interactive = false;
}
console.log("Bower: Using cwd: ", opts.cwd || process.cwd());
console.log("Bower: Using bower dir: ", dir);
const logger = new Logger();
logger.on("log", log => console.log(["Bower", log.message].join(" ")));
let config = opts;
const options = {};
config = mout.object.deepFillIn(config || {}, defaultConfig);
if (options.save == null) {
  options.save = config.defaultSave;
}
const project = new Project(config, logger);
project._json = bowerjson;
project._jsonFile = "bower.json";
project.saveJson = () => Q.resolve();
const tracker = new Tracker(config);
const decEndpoints = [];
let EXITCONDITION = false;
tracker.trackDecomposedEndpoints("install", decEndpoints);
project.install(decEndpoints, options, config).then(
  function(installed) {
    let summary =
      "BOWERDEPS = (typeof BOWERDEPS === 'undefined') ? {}: BOWERDEPS;";
    try {
      let v;
      for (var k in project._manager._installed) {
        v = project._manager._installed[k];
        if (v != null) {
          console.log("installed: " + k);
          installed[k] = { pkgMeta: v };
        }
      }
      function extract_meta(a) {
        const r = {};
        r["license"] = config.deps[a["name"]]["license"];
        for (let k of [
          "name",
          "license",
          "homepage",
          "description",
          "version"
        ]) {
          if (a.hasOwnProperty(k)) r[k] = a[k];
        }
        if (typeof r["license"] === "undefined") {
          console.log("warning: no license for " + k);
        }
        return r;
      }
      for (k in opts.deps) {
        v = opts.deps[k];
        if (installed.hasOwnProperty(k)) {
          summary += `\nBOWERDEPS['${k}'] = `;
          var meta = extract_meta(installed[k].pkgMeta);
          summary += JSON.stringify(meta, null, 1);
          opts.deps[k].meta = meta;
        }
      }
      fs.writeFileSync(summaryfile, summary);
      fs.writeFileSync(
        metadatafile,
        JSON.stringify(
          {
            deps: opts.deps,
            js_files: file_list
          },
          null,
          1
        )
      );
      let gitcmd = "git add -f ";
      console.log(to_add_file_list);
      to_add_file_list.forEach(gl => {
        glob.sync(gl).forEach(fn => {
          console.log("vendoring  ", fn);
          gitcmd += " " + fn;
        });
      });
      exec(gitcmd);
    } catch (e) {
      console.log(e);
    }
    return (EXITCONDITION = true);
  },
  function(error) {
    console.log("error!!", error);
    return (EXITCONDITION = true);
  }
);
function wait() {
  if (!EXITCONDITION) {
    return setTimeout(wait, 100);
  }
}
wait();
