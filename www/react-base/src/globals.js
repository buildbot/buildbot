import jquery from 'jquery';

// For some reason webpack ProvidePlugin has trouble injecting jquery to global scope so that e.g. Bootstrap can use
// it without importing. The following is a workaround.
window.$ = jquery;
window.jQuery = jquery;