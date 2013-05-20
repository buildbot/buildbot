module.exports = (grunt) ->

    grunt.registerMultiTask 'requiregen', 'generate requirejs dependency tree', ->
        options = @options
                    order: ['.*']
        for group in @files
            order = options.order # list of regexp matching each layer
            layers = []          # the list of list of modules, ordered by load time
            choosen_modules = {} # remember which module was already choosen
            for re in order
                modules = []
                matcher = new RegExp "^#{re}$"
                for s in group.src
                    s = s.toString().slice(0, -3) # remove ".js" from filename
                    if choosen_modules.hasOwnProperty(s)
                        continue
                    if matcher.test(s)
                        choosen_modules[s] = 1
                        modules.push(s)
                layers.push modules
                grunt.log.writeln('modules "' + modules.join(", ") + '" loaded together.');
            last_layer = []
            shim = {}
            for layer in layers
                for module in layer
                    shim[module] = last_layer
                last_layer = layer
            shim = JSON.stringify(shim, null, 1)
            last_layer = JSON.stringify(last_layer, null, 1)
            requirejs_code = "require( { shim: #{shim} }, #{last_layer} )"
            # Write the destination file.
            grunt.file.write(group.dest, requirejs_code);
            # Print a success message.
            grunt.log.writeln('File "' + group.dest + '" created.');
