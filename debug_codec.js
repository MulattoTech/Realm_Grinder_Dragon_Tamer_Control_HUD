const fs = require('fs');
global.pako = require('./pako.js');
global.window = global;
global.document = {};
global.jQuery = {};
global.atob = str => Buffer.from(str, 'base64').toString('binary');
global.btoa = str => Buffer.from(str, 'binary').toString('base64');

require('./savecodec2.js');

// Intercept parseItem to see which item failed
const origParseItem = window.SaveHandler._Format.parseItem;
// Let's check how Format is exposed
console.log(Object.keys(window.SaveHandler));
