'use strict';

const { test } = require('node:test');
const assert = require('node:assert/strict');
const { parseQueryString } = require('./querystring.js');

test('simple pairs', () => {
  assert.deepEqual(parseQueryString('a=1&b=2'), { a: '1', b: '2' });
});

test('a leading question mark is stripped', () => {
  assert.deepEqual(parseQueryString('?a=1'), { a: '1' });
});

test('percent decoding', () => {
  assert.deepEqual(parseQueryString('q=a%20b'), { q: 'a b' });
});

test('plus decodes to a space', () => {
  assert.deepEqual(parseQueryString('q=a+b'), { q: 'a b' });
});

test('a key with no value', () => {
  assert.deepEqual(parseQueryString('a'), { a: '' });
});

test('a repeated key becomes an array', () => {
  assert.deepEqual(parseQueryString('a=1&a=2'), { a: ['1', '2'] });
});

test('a repeated key keeps order', () => {
  assert.deepEqual(parseQueryString('a=3&a=1&a=2').a, ['3', '1', '2']);
});

test('a single occurrence stays a string', () => {
  assert.equal(typeof parseQueryString('a=1').a, 'string');
});

test('empty inputs', () => {
  assert.deepEqual(parseQueryString(''), {});
  assert.deepEqual(parseQueryString('?'), {});
});

test('empty segments are skipped', () => {
  assert.deepEqual(parseQueryString('a=1&&b=2'), { a: '1', b: '2' });
});

test('a value may contain equals signs', () => {
  assert.deepEqual(parseQueryString('a=b=c'), { a: 'b=c' });
});

test('a key with no value plus a real value', () => {
  assert.deepEqual(parseQueryString('a&b=2'), { a: '', b: '2' });
});

test('a malformed escape throws', () => {
  assert.throws(() => parseQueryString('a=%'), URIError);
});
