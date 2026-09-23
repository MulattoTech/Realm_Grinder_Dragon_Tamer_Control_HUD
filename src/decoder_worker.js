/**
 * Persistent High-Performance Realm Grinder Save Decoder Worker
 * Reads single-line raw save strings from stdin and writes parsed JSON to stdout.
 * Eliminates subprocess spawning overhead completely (sub-millisecond decode).
 */
const readline = require('readline');
const path = require('path');

const rootDir = path.resolve(__dirname, '..');
global.pako = require(path.join(rootDir, 'pako.js'));
global.window = global;
global.document = {};
global.jQuery = {};
global.atob = str => Buffer.from(str, 'base64').toString('binary');
global.btoa = str => Buffer.from(str, 'binary').toString('base64');
require(path.join(rootDir, 'savecodec2_debug.js'));

const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout,
    terminal: false
});

rl.on('line', (line) => {
    const s = line.trim().replace(/\0+$/, '');
    if (!s) {
        process.stdout.write("{}\n");
        return;
    }
    try {
        const d = window.SaveHandler.Decode(s);
        process.stdout.write(JSON.stringify(d) + "\n");
    } catch (err) {
        process.stdout.write(JSON.stringify({ error: err.message || String(err) }) + "\n");
    }
});
