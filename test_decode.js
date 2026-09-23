const fs = require('fs');
global.pako = require('./pako.js');
global.window = global;
global.document = {};
global.jQuery = {};
global.atob = str => Buffer.from(str, 'base64').toString('binary');
global.btoa = str => Buffer.from(str, 'binary').toString('base64');

require('./savecodec2.js');

let saveStr = fs.readFileSync('test_save.txt', 'utf8').trim();
if (saveStr.endsWith('\u0000')) {
    saveStr = saveStr.slice(0, -1);
}
console.log('Cleaned len:', saveStr.length);
console.log('Ends with $e:', saveStr.endsWith('$e'));
try {
    const decoded = window.SaveHandler.Decode(saveStr);
    console.log('Decode success!');
    console.log('saveVersion:', decoded.saveVersion);
    console.log('reincarnation:', decoded.reincarnation);
    console.log('gems:', decoded.gems);
    console.log('excavations:', decoded.excavations);
    console.log('alignment:', decoded.alignment);
    console.log('faction:', decoded.faction);
    console.log('factionCoins:', decoded.factionCoins);
    console.log('artifacts:', decoded.artifacts ? Object.keys(decoded.artifacts).length : 'none');
    fs.writeFileSync('decoded_save_clean.json', JSON.stringify(decoded, null, 2));
    console.log('Wrote decoded_save_clean.json successfully!');
} catch (e) {
    console.error('Decode error:', e);
}
