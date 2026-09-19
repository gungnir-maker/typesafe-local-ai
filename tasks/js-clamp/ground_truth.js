'use strict';

const { test } = require('node:test');
const assert = require('node:assert/strict');
const { clamp } = require('./range.js');

test('value inside the range is unchanged', () => {
  assert.equal(clamp(5, 1, 10), 5);
});

test('value below the minimum becomes the minimum', () => {
  assert.equal(clamp(0, 1, 10), 1);
});

test('value above the maximum becomes the maximum', () => {
  assert.equal(clamp(99, 1, 10), 10);
});

test('bounds are inclusive', () => {
  assert.equal(clamp(1, 1, 10), 1);
  assert.equal(clamp(10, 1, 10), 10);
});

test('fractional values are supported', () => {
  assert.equal(clamp(-0.5, -1, 1), -0.5);
  assert.equal(clamp(0.5, 0, 0.25), 0.25);
});

test('negative ranges work', () => {
  assert.equal(clamp(-5, -10, -1), -5);
  assert.equal(clamp(-20, -10, -1), -10);
});

test('non-finite numbers are refused', () => {
  for (const bad of [NaN, Infinity, -Infinity]) {
    assert.throws(() => clamp(bad, 0, 1), TypeError);
  }
});

test('non-numbers are refused', () => {
  for (const bad of ['5', null, undefined, {}, []]) {
    assert.throws(() => clamp(bad, 0, 1), TypeError);
  }
});

test('an inverted range is refused', () => {
  assert.throws(() => clamp(5, 10, 1), RangeError);
});
