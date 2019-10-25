const pug = require('pug');
const path = require('path')
var loaderUtils = require("loader-utils");

/* ultra simple loader that only support our simple usecase 
  pug-loader is much more complicated, but do support lot of features, 
  including require inside template, which we don't really need.
*/

module.exports = function() {
  var fileName = this.resourcePath;
  var code = pug.compileFile(fileName);
  var content = code();
  var pluginName = loaderUtils.getOptions(this).pluginName;

  // compute template name (as defined by ancient gulp based build system)
  var tplName = "views/" + path.parse(fileName).name.replace(/.tpl$/,'') + ".html";
  if (pluginName != "buildbot-www") {
    tplName = pluginName + "/" + tplName;
  }
  // search for custom_templates (we use T as a short name to avoid consume to much bytes)
  content = `module.exports = window.T['${tplName}'] || ${JSON.stringify(content)};`;
  return content;
}