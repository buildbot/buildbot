/**
 * This file is referenced by the `dojoBuild` key in `package.json` and provides extra hinting specific to the Dojo
 * build system about how certain files in the package need to be handled at build time. Build profiles for the
 * application itself are stored in the `profiles` directory.
 */

var profile = {
    // Resource tags are functions that provide hints to the build system about the way files should be processed.
    // Each of these functions is called once for every file in the package directory. The first argument passed to
    // the function is the filename of the file, and the second argument is the computed AMD module ID of the file.
    resourceTags: {
        // Files that contain test code and should be excluded when the `copyTests` build flag exists and is `false`.
        // It is strongly recommended that the `mini` build flag be used instead of `copyTests`. Therefore, no files
        // are marked with the `test` tag here.
        test: function (filename, mid) {
            return false;
        },

        // Files that should be copied as-is without being modified by the build system.
        // All files in the `app/resources` directory that are not CSS files are marked as copy-only, since these files
        // are typically binaries (images, etc.) and may be corrupted by the build system if it attempts to process
        // them and naively assumes they are scripts.
        copyOnly: function (filename, mid) {
            return (/^bb\/resources\/img\//.test(filename) || /^bb\/resources\/css\//.test(filename));
        },

        // Files that are AMD modules.
        // All JavaScript in this package should be AMD modules if you are starting a new project. If you are copying
        // any legacy scripts from an existing project, those legacy scripts should not be given the `amd` tag.
        amd: function (filename, mid) {
            return !this.copyOnly(filename, mid) && /\.js$/.test(filename);
        },

        // Files that should not be copied when the `mini` build flag is set to true.
        // In this case, we are excluding this package configuration file which is not necessary in a built copy of
        // the application.
        miniExclude: function (filename, mid) {
            return mid in {
                'bb/package': 1
            };
        }
    }
};
