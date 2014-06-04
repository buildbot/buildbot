/*!
 * URI.js - Mutating URLs
 * jQuery Plugin
 *
 * Version: 1.13.2
 *
 * Author: Rodney Rehm
 * Web: http://medialize.github.io/URI.js/jquery-uri-plugin.html
 *
 * Licensed under
 *   MIT License http://www.opensource.org/licenses/mit-license
 *   GPL v3 http://opensource.org/licenses/GPL-3.0
 *
 */

(function(e,t){typeof exports=="object"?module.exports=t(require("jquery","./URI")):typeof define=="function"&&define.amd?define(["jquery","./URI"],t):t(e.jQuery,e.URI)})(this,function(e,t){function i(e){return e.replace(/([.*+?^=!:${}()|[\]\/\\])/g,"\\$1")}function s(e){var n=e.nodeName.toLowerCase(),r=t.domAttributes[n];return n==="input"&&e.type!=="image"?undefined:r}function o(t){return{get:function(n){return e(n).uri()[t]()},set:function(n,r){return e(n).uri()[t](r),r}}}function l(t,i){var o,u,a;return!s(t)||!i?!1:(o=i.match(f),!o||!o[5]&&o[2]!==":"&&!r[o[2]]?!1:(a=e(t).uri(),o[5]?a.is(o[5]):o[2]===":"?(u=o[1].toLowerCase()+":",r[u]?r[u](a,o[4]):!1):(u=o[1].toLowerCase(),n[u]?r[o[2]](a[u](),o[4],u):!1)))}var n={},r={"=":function(e,t){return e===t},"^=":function(e,t){return!!(e+"").match(new RegExp("^"+i(t),"i"))},"$=":function(e,t){return!!(e+"").match(new RegExp(i(t)+"$","i"))},"*=":function(e,t,n){return n==="directory"&&(e+="/"),!!(e+"").match(new RegExp(i(t),"i"))},"equals:":function(e,t){return e.equals(t)},"is:":function(e,t){return e.is(t)}};e.each("authority directory domain filename fragment hash host hostname href password path pathname port protocol query resource scheme search subdomain suffix tld username".split(" "),function(t,r){n[r]=!0,e.attrHooks["uri:"+r]=o(r)});var u={get:function(t){return e(t).uri()},set:function(t,n){return e(t).uri().href(n).toString()}};e.each(["src","href","action","uri","cite"],function(t,n){e.attrHooks[n]={set:u.set}}),e.attrHooks.uri.get=u.get,e.fn.uri=function(e){var n=this.first(),r=n.get(0),i=s(r);if(!i)throw new Error('Element "'+r.nodeName+'" does not have either property: href, src, action, cite');if(e!==undefined){var o=n.data("uri");if(o)return o.href(e);e instanceof t||(e=t(e||""))}else{e=n.data("uri");if(e)return e;e=t(n.attr(i)||"")}return e._dom_element=r,e._dom_attribute=i,e.normalize(),n.data("uri",e),e},t.prototype.build=function(e){if(this._dom_element)this._string=t.build(this._parts),this._deferred_build=!1,this._dom_element.setAttribute(this._dom_attribute,this._string),this._dom_element[this._dom_attribute]=this._string;else if(e===!0)this._deferred_build=!0;else if(e===undefined||this._deferred_build)this._string=t.build(this._parts),this._deferred_build=!1;return this};var a,f=/^([a-zA-Z]+)\s*([\^\$*]?=|:)\s*(['"]?)(.+)\3|^\s*([a-zA-Z0-9]+)\s*$/;return e.expr.createPseudo?a=e.expr.createPseudo(function(e){return function(t){return l(t,e)}}):a=function(e,t,n){return l(e,n[3])},e.expr[":"].uri=a,e});