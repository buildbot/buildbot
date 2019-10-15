const ngClassify = require('ng-classify')
const fs = require('fs')
const util = require('util');

const readFile = util.promisify(fs.readFile)
const writeFile = util.promisify(fs.writeFile)

async function processNgClassify(args) {
    for (var i in args) {
        var path = args[i];
        console.log(path);
        data = await readFile(path, 'utf8');

        data = ngClassify(data);

        await writeFile(path, data);
    }
}

var args = process.argv.slice(2);
processNgClassify(args);
