'use strict';

const { test } = require('node:test');
const assert = require('node:assert/strict');
const { slugify } = require('./slug.js');

test('basic slug', () => {
  assert.equal(slugify('Hello, World!', 60), 'hello-world');
});

test('collapses runs of dashes', () => {
  assert.equal(slugify('a---b', 60), 'a-b');
});

test('strips edge dashes', () => {
  assert.equal(slugify('--x--', 60), 'x');
});

test('digits survive', () => {
  assert.equal(slugify('Version 2.0', 60), 'version-2-0');
});

test('empty input', () => {
  assert.equal(slugify('', 60), '');
});

test('punctuation only', () => {
  assert.equal(slugify('!!!', 60), '');
});

test('truncates to the maximum length', () => {
  assert.equal(slugify('aaaa bbbb cccc', 8), 'aaaa-bbb');
});

test('truncation does not leave a trailing dash', () => {
  assert.equal(slugify('aaa bbb', 4), 'aaa');
  assert.equal(slugify('aaaa bbbb', 5), 'aaaa');
});

test('truncation keeps a usable result when the cut is clean', () => {
  assert.equal(slugify('aaa bbb', 5), 'aaa-b');
});

test('maxLength of zero gives an empty string', () => {
  assert.equal(slugify('abc', 0), '');
});

test('a negative maxLength is refused', () => {
  assert.throws(() => slugify('abc', -1), RangeError);
});

test('a non-string text is refused', () => {
  for (const bad of [null, undefined, 3, [], {}]) {
    assert.throws(() => slugify(bad, 10), TypeError);
  }
});
