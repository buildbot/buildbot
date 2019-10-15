/*
 * decaffeinate suggestions:
 * DS102: Remove unnecessary code created because of implicit returns
 * DS207: Consider shorter variations of null checks
 * Full docs: https://github.com/decaffeinate/decaffeinate/blob/master/docs/suggestions.md
 */
/*
    Favicon service
*/

class FaviconService {
    constructor(RESULTS_COLOR, resultsService, $http){
        return {
            setFavIcon(build_or_step){
                if ((build_or_step == null)) {
                    // by default, we take the original icon
                    document.getElementById('bbicon').href = "img/icon.png";
                    return;
                }

                $http.get("img/icon16.svg").then(function(data) {
                    // if there is a build or step associated to this page
                    // we color the icon with result's color
                    // We the raster the SVG to PNG, so that it can be displayed as favicon
                    let color;
                    ({ data } = data);
                    const canvas = document.createElement('canvas');
                    canvas.width = (canvas.height = '300');
                    const ctx = canvas.getContext('2d');
                    const results_text = resultsService.results2text(build_or_step);
                    if (_.has(RESULTS_COLOR, results_text)) {
                        color = RESULTS_COLOR[results_text];
                    } else {
                        color = '#E7D100';
                    }
                    data = data.replace("#8da6d8", color);
                    const DOMURL = window.URL || window.webkitURL || window;
                    const img = new Image;
                    const svg = new Blob([ data ], {type: 'image/svg+xml'});
                    const url = DOMURL.createObjectURL(svg);

                    img.onload = function() {
                        ctx.drawImage(img, 0, 0);
                        document.getElementById('bbicon').href = canvas.toDataURL();
                        return DOMURL.revokeObjectURL(url);
                    };

                    img.crossOrigin = 'Anonymous';
                    img.src = url;
                });
            }
        };
    }
}


angular.module('common')
.factory('faviconService', ['RESULTS_COLOR', 'resultsService', '$http', FaviconService]);
