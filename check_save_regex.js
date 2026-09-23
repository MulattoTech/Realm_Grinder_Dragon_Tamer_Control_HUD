const fs = require('fs');
const s = fs.readFileSync('test_save.txt', 'utf8').trim();
console.log('len:', s.length);
console.log('starts:', s.slice(0, 10));
console.log('ends:', JSON.stringify(s.slice(-10)));
const re = /^\$([0-9]{2})s([\s\S]*)\$e$/;
console.log('test struct:', re.test(s));
