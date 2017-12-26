###
    Favicon service
###

class FaviconService extends Factory('common')
    constructor: (RESULTS_COLOR, resultsService, $http)->
        return {
            setFavIcon: (build_or_step)->
                if not build_or_step?
                    # by default, we take the original icon
                    document.getElementById('bbicon').href = "img/icon.png"
                    return

                $http.get("img/icon16.svg").then (data) ->
                    # if there is a build or step associated to this page
                    # we color the icon with result's color
                    # We the raster the SVG to PNG, so that it can be displayed as favicon
                    data = data.data
                    canvas = document.createElement('canvas')
                    canvas.width = canvas.height = '300'
                    ctx = canvas.getContext('2d')
                    results_text = resultsService.results2text(build_or_step)
                    if _.has(RESULTS_COLOR, results_text)
                        color = RESULTS_COLOR[results_text]
                    else
                        color = '#E7D100'
                    data = data.replace("#8da6d8", color)
                    DOMURL = window.URL or window.webkitURL or window
                    img = new Image
                    svg = new Blob([ data ], type: 'image/svg+xml')
                    url = DOMURL.createObjectURL(svg)

                    img.onload = ->
                        ctx.drawImage(img, 0, 0)
                        document.getElementById('bbicon').href = canvas.toDataURL()
                        DOMURL.revokeObjectURL url

                    img.crossOrigin = 'Anonymous'
                    img.src = url
        }
