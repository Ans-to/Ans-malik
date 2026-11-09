import {test} from 'node:test';
import assert from 'node:assert/strict';
import {warpTime} from '../web/morph/timewarp.mjs';
test('audio to GSAP mapping remains continuous and hits spoken anchors',()=>{
 const marks=[{real:0,virtual:0},{real:2.06,virtual:2},{real:4.76,virtual:4},{real:8.64,virtual:6}];
 for(const m of marks)assert.ok(Math.abs(warpTime(m.real,marks)-m.virtual)<1e-10);
 assert.ok(Math.abs(warpTime(3.41,marks)-3)<1e-10);
 for(let t=0;t<8.63;t+=.01)assert.ok(warpTime(t+.01,marks)>=warpTime(t,marks));
});
