'use strict';

const { test } = require('node:test');
const assert = require('node:assert/strict');
const { chunkArray } = require('./chunk.js');

test('splits with a remainder', () => {
  assert.deepEqual(chunkArray([1, 2, 3, 4, 5], 2), [[1, 2], [3, 4], [5]]);
});

test('splits evenly', () => {
  assert.deepEqual(chunkArray([1, 2, 3, 4], 2), [[1, 2], [3, 4]]);
});

test('empty input gives an empty array', () => {
  assert.deepEqual(chunkArray([], 3), []);
});

test('size larger than the input', () => {
  assert.deepEqual(chunkArray([1, 2], 5), [[1, 2]]);
});

test('size of one', () => {
  assert.deepEqual(chunkArray([1, 2, 3], 1), [[1], [2], [3]]);
});

test('the input array is not modified', () => {
  const input = [1, 2, 3, 4, 5];
  const snapshot = input.slice();
  chunkArray(input, 2);
  assert.deepEqual(input, snapshot);
});

test('a non-positive or fractional size is refused', () => {
  for (const bad of [0, -1, 2.5, NaN]) {
    assert.throws(() => chunkArray([1, 2], bad), RangeError);
  }
});

test('a non-integer size is refused', () => {
  assert.throws(() => chunkArray([1, 2], '2'), RangeError);
});

test('a non-array is refused', () => {
  for (const bad of ['abc', null, undefined, 3, {}]) {
    assert.throws(() => chunkArray(bad, 2), TypeError);
  }
});
