###
    Favicon service
###

class FaviconService extends Factory('common')
    constructor: (RESULTS_COLOR, resultsService)->
        return {
            setFavIcon: (build_or_step)->
                canvas = document.createElement('canvas')
                canvas.width = '300'
                canvas.height = '300'
                ctx = canvas.getContext('2d')
                # the svg HAS to be embedded in the JS, or we hit weird CORS restrictions
                # with manipulating Canvas.
                data = '<svg xmlns="http://www.w3.org/2000/svg" fill-rule="evenodd" height="300" width="300"><path d="M26.256 203.044v-39.707l90.728 84.287v39.707z"/><path d="M116.984 247.624l123.91-30.863v39.706l-123.998 30.864v-39.707zm123.91-30.863v39.706l33.182-115.06v-39.706z"/><path d="M183.436 17.504l90.64 84.197-33.183 115.06-123.997 30.863-90.64-84.287 33.182-114.97zm-3.319 66.87c28.642 15.341 38.422 49.363 21.83 75.985-16.416 26.531-53.09 35.646-81.733 20.304-28.641-15.341-38.421-49.363-21.83-75.894 16.33-26.622 53.004-35.826 81.646-20.485z" fill="NUTCOLOR"/><path d="M92.795 148.356a48.9 50.536 0 0 1 5.502-43.587c16.59-26.622 53.266-35.736 81.82-20.395 24.45 13.176 35.191 39.978 27.42 64.073a55.013 56.853 0 0 0-27.42-32.307c-28.641-15.342-65.316-6.227-81.82 20.395a51.17 52.882 0 0 0-5.502 11.821z"/><ellipse ry="17.018" rx="16.317" cy="63.209" cx="198.379" fill="#fff"/></svg>'
                color = '#8da6d8'
                if build_or_step?
                    results_text = resultsService.results2text(build_or_step)
                    if _.has(RESULTS_COLOR, results_text)
                        color = RESULTS_COLOR[results_text]
                    else
                        color = '#E7D100'
                data = data.replace("NUTCOLOR", color)
                DOMURL = window.URL or window.webkitURL or window
                img = new Image
                svg = new Blob([ data ], type: 'image/svg+xml')
                url = DOMURL.createObjectURL(svg)

                img.onload = ->
                    ctx.drawImage img, 0, 0
                    document.getElementById('bbicon').href = canvas.toDataURL()
                    DOMURL.revokeObjectURL url

                img.crossOrigin = 'Anonymous'
                img.src = url
        }
