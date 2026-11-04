import test from 'node:test';
import assert from 'node:assert/strict';
import {paletteVariables, cameraDrift, ease} from '../web/design.js';
test('palette and motion defaults', () => {
  assert.equal(paletteVariables('obsidian_documentary')['--background'], '#090B10');
  assert.throws(() => paletteVariables('missing'));
  assert.notDeepEqual(cameraDrift(0), cameraDrift(1));
  assert.match(ease, /cubic-bezier/);
});
