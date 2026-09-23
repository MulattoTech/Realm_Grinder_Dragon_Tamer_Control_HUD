const fs = require('fs');
global.pako = require('./pako.js');
global.window = global;
global.document = {};
global.jQuery = {};
global.atob = str => Buffer.from(str, 'base64').toString('binary');
global.btoa = str => Buffer.from(str, 'binary').toString('base64');

require('./savecodec2_debug.js');

let saveStr = fs.readFileSync('test_save.txt', 'utf8').trim();
if (saveStr.endsWith('\u0000')) saveStr = saveStr.slice(0, -1);

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
    console.log('artifacts count:', decoded.artifacts ? Object.keys(decoded.artifacts).length : 'none');
    console.log('upgrades count:', decoded.upgrades ? Object.keys(decoded.upgrades).length : 'none');
    console.log('trophies count:', decoded.trophies ? Object.keys(decoded.trophies).length : 'none');
    console.log('spells count:', decoded.spells ? Object.keys(decoded.spells).length : 'none');
    fs.writeFileSync('decoded_save_clean.json', JSON.stringify(decoded, null, 2));
    console.log('Wrote decoded_save_clean.json successfully!');
} catch (e) {
    console.error('Decode error:', e);
}
