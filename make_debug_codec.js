const fs = require('fs');
let code = fs.readFileSync('savecodec2.js', 'utf8');

// The original lines around 312:
// \t\t\tthis.parseItem = function(parent, item) {
// \r\n\t\t\t\t// Condition checks

code = code.replace(
    /this\.parseItem = function\(parent, item\) \{[\r\n\s]+\/\/ Condition checks/,
    `this.parseItem = function(parent, item) {
\t\t\t\tif (!item) {
\t\t\t\t\treturn;
\t\t\t\t}
\t\t\t\t// Condition checks`
);

fs.writeFileSync('savecodec2_debug.js', code);
console.log('Successfully patched savecodec2_debug.js');
