/*!
 * URI.js - Mutating URLs
 * IPv6 Support
 *
 * Version: 1.13.2
 *
 * Author: Rodney Rehm
 * Web: http://medialize.github.io/URI.js/
 *
 * Licensed under
 *   MIT License http://www.opensource.org/licenses/mit-license
 *   GPL v3 http://opensource.org/licenses/GPL-3.0
 *
 */

(function(e,t){typeof exports=="object"?module.exports=t():typeof define=="function"&&define.amd?define(t):e.IPv6=t(e)})(this,function(e){function n(e){var t=e.toLowerCase(),n=t.split(":"),r=n.length,i=8;n[0]===""&&n[1]===""&&n[2]===""?(n.shift(),n.shift()):n[0]===""&&n[1]===""?n.shift():n[r-1]===""&&n[r-2]===""&&n.pop(),r=n.length,n[r-1].indexOf(".")!==-1&&(i=7);var s;for(s=0;s<r;s++)if(n[s]==="")break;if(s<i){n.splice(s,1,"0000");while(n.length<i)n.splice(s,0,"0000");r=n.length}var o;for(var u=0;u<i;u++){o=n[u].split("");for(var a=0;a<3;a++){if(!(o[0]==="0"&&o.length>1))break;o.splice(0,1)}n[u]=o.join("")}var f=-1,l=0,c=0,h=-1,p=!1;for(u=0;u<i;u++)p?n[u]==="0"?c+=1:(p=!1,c>l&&(f=h,l=c)):n[u]==="0"&&(p=!0,h=u,c=1);c>l&&(f=h,l=c),l>1&&n.splice(f,l,""),r=n.length;var d="";n[0]===""&&(d=":");for(u=0;u<r;u++){d+=n[u];if(u===r-1)break;d+=":"}return n[r-1]===""&&(d+=":"),d}function r(){return e.IPv6===this&&(e.IPv6=t),this}var t=e&&e.IPv6;return{best:n,noConflict:r}});