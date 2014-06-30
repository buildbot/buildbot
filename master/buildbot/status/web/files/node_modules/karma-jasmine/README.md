# karma-jasmine [![Build Status](https://travis-ci.org/karma-runner/karma-jasmine.png?branch=master)](https://travis-ci.org/karma-runner/karma-jasmine)

> Adapter for the [Jasmine](http://pivotal.github.io/jasmine/) testing framework.


## Installation

### Jasmine 1.3 ([docs](http://pivotal.github.io/jasmine/))

The easiest way is to keep `karma-jasmine` as a devDependency in your `package.json`.

```json
{
  "devDependencies": {
    "karma": "~0.10",
    "karma-jasmine": "~0.1.0"
  }
}
```

You can simple do it by:
```bash
npm install karma-jasmine --save-dev
```


### Jasmine 2.0 ([docs](http://jasmine.github.io/2.0/introduction.html))

The easiest way is to keep `karma-jasmine` as a devDependency in your `package.json`.
```json
{
  "devDependencies": {
    "karma": "~0.10",
    "karma-jasmine": "~0.2.0"
  }
}
```

You can simple do it by:
```bash
npm install karma-jasmine@2_0 --save-dev
```


## Configuration
```js
// karma.conf.js
module.exports = function(config) {
  config.set({
    frameworks: ['jasmine'],

    files: [
      '*.js'
    ]
  });
};
```

----

For more information on Karma see the [homepage].


[homepage]: http://karma-runner.github.com
