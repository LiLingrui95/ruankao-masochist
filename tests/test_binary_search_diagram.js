'use strict';

const assert = require('node:assert/strict');
const {values, buildTrace} = require('../static/binary-search.js');

assert.deepEqual(values, [4, 11, 19, 28, 36, 47, 59]);

const found = buildTrace(47);
const foundComparisons = found.filter(step => step.phase === 'compare');
assert.deepEqual(foundComparisons.map(step => step.mid), [3, 5]);
assert.equal(found.at(-1).result, 5);

const missing = buildTrace(35);
assert.deepEqual(missing.filter(step => step.phase === 'compare').map(step => step.mid), [3, 5, 4]);
assert.deepEqual(missing.at(-1), {
  phase: 'terminal', low: 4, high: 3, mid: null, target: 35,
  message: '区间为空（low=4，high=3），返回 -1。', result: -1
});

assert.notEqual(buildTrace(47), buildTrace(47));
assert.throws(() => buildTrace(12), /Unsupported/);
