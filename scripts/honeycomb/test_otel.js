'use strict';
process.env.NODE_PATH = '/usr/lib/node_modules';
require('module').Module._initPaths();
try {
  const r = require('@opentelemetry/resources');
  console.log('resources exports:', Object.keys(r).filter(k => /resource/i.test(k)).join(', '));
  const { resourceFromAttributes } = r;
  if (resourceFromAttributes) {
    console.log('USE: resourceFromAttributes() -- new API');
  }
  if (r.Resource) {
    console.log('USE: new Resource() -- old API');
  }
} catch (e) {
  console.log('ERROR:', e.message);
}
