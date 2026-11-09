import {build} from 'esbuild';
import {createServer} from 'node:http';
import {readFile} from 'node:fs/promises';
import {resolve,extname,relative} from 'node:path';
import {spawn,spawnSync} from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import zlib from 'node:zlib';
import {once} from 'node:events';
import {PNG} from 'pngjs';
import chromium from '@sparticuz/chromium';
import puppeteer from 'puppeteer-core';

const args=Object.fromEntries(process.argv.slice(2).map(x=>{let i=x.indexOf('=');return [x.slice(0,i),x.slice(i+1)]}));
const libdir=resolve(os.tmpdir(),'cinema-chrome-libs');if(!fs.existsSync(resolve(libdir,'lib','libnspr4.so'))){fs.mkdirSync(libdir,{recursive:true});const archive=zlib.brotliDecompressSync(fs.readFileSync(resolve('node_modules/@sparticuz/chromium/bin/al2023.tar.br')));if(spawnSync('tar',['-xf','-','-C',libdir],{input:archive}).status!==0)throw Error('Chromium libraries unavailable')}process.env.LD_LIBRARY_PATH=resolve(libdir,'lib')+(process.env.LD_LIBRARY_PATH?':'+process.env.LD_LIBRARY_PATH:'');
const root=process.cwd(), data=JSON.parse(await readFile(args.data,'utf8'));
const width=+(args.width||1920),height=+(args.height||1080),fps=60,frames=+(args.frames||data.frames);
await build({entryPoints:['web/semantic/app.jsx'],bundle:true,external:['/shared_workspace/*'],format:'esm',target:'chrome110',outfile:'web/semantic/bundle.js',jsx:'automatic',define:{'process.env.NODE_ENV':'"production"'}});
const types={'.html':'text/html','.js':'application/javascript','.css':'text/css','.png':'image/png','.ttf':'font/ttf'};
const server=createServer(async(req,res)=>{try{const pathname=decodeURIComponent(new URL(req.url,'http://localhost').pathname);if(pathname==='/__data'){res.writeHead(200,{'Content-Type':'application/json'});res.end(JSON.stringify(data));return}let path=resolve(root,'.'+(pathname==='/'?'/web/semantic/index.html':pathname));if(relative(root,path).startsWith('..'))throw Error('outside root');const body=await readFile(path);res.writeHead(200,{'Content-Type':types[extname(path)]||'application/octet-stream'});res.end(body)}catch{res.writeHead(404);res.end('Not found')}});
await new Promise(r=>server.listen(0,'127.0.0.1',r));const port=server.address().port;
let browser;
async function auditTextPixels(page,frame){
 const expected=await page.evaluate(()=>{document.documentElement.classList.add('text-audit-mask');const focal=document.querySelector('[data-focal-object]');return !!(focal&&Number(getComputedStyle(focal).opacity)>0&&focal.querySelector('[data-audit-text]'));});
 const image=PNG.sync.read(await page.screenshot({type:'png'}));
 await page.evaluate(()=>document.documentElement.classList.remove('text-audit-mask'));
 const left=Math.ceil(260*image.width/1920),right=Math.floor(1660*image.width/1920),top=Math.ceil(150*image.height/1080),bottom=Math.floor(930*image.height/1080),p=image.data;
 let sawText=false;for(let y=0;y<image.height;y++){for(let x=0;x<image.width;x++){const inside=y>=top&&y<bottom&&x>=left&&x<right;if(inside&&sawText)continue;const i=(y*image.width+x)*4,lit=p[i]>2||p[i+1]>2||p[i+2]>2;if(inside){if(lit)sawText=true}else if(lit)throw Error(`Text pixels in no-fly zone at frame ${frame}, (${x},${y})`)}}if(expected&&!sawText)throw Error(`Text mask was unexpectedly empty at frame ${frame}`);
}

try{
 browser=await puppeteer.launch({executablePath:process.env.CHROMIUM_PATH||await chromium.executablePath(),headless:true,args:[...chromium.args,'--no-sandbox','--disable-dev-shm-usage','--use-gl=angle','--use-angle=swiftshader']});
 const page=await browser.newPage();page.on('pageerror',e=>console.error('BROWSER ERROR',e));await page.setViewport({width,height,deviceScaleFactor:1});await page.goto(`http://127.0.0.1:${port}/`,{waitUntil:'networkidle0'});await page.waitForFunction('window.ready === true',{timeout:60000});await page.addStyleTag({content:'html.text-audit-mask,html.text-audit-mask body,html.text-audit-mask #root{background:#000!important}html.text-audit-mask *{visibility:hidden!important}html.text-audit-mask [data-audit-text]{visibility:visible!important;color:#fff!important;text-shadow:none!important}'});
 if(args.samples){for(const cue of data.cues){const frame=Math.min(frames-1,cue.first_frame+12);await page.evaluate(f=>window.renderFrame(f),frame);await auditTextPixels(page,frame);await page.screenshot({path:`${args.samples}-${cue.id}-${frame}.png`});}console.log('Cue samples saved');}
 else {
  const decoder=spawn(args.ffmpeg,['-v','error','-f','image2pipe','-vcodec','png','-i','pipe:0','-f','rawvideo','-pix_fmt','rgb24','pipe:1'],{stdio:['pipe','pipe','inherit']});
  const encoder=spawn(args.ffmpeg,['-v','warning','-y','-f','rawvideo','-pix_fmt','rgb24','-s',`${width}x${height}`,'-r',String(fps),'-i','pipe:0','-i',args.audio,'-frames:v',String(frames),'-c:v','libx264','-preset','veryfast','-crf','16','-pix_fmt','yuv420p','-c:a',args.copyaudio==='1'?'copy':'aac',...(args.copyaudio==='1'?[]:['-b:a','192k']),'-movflags','+faststart',args.output],{stdio:['pipe','inherit','inherit']});
  decoder.stdout.pipe(encoder.stdin);for(const p of [decoder,encoder])p.on('error',e=>console.error(e));
  for(let i=0;i<frames;i++){await page.evaluate(f=>window.renderFrame(f),i);await auditTextPixels(page,i);const shot=await page.screenshot({type:'png'});if(!decoder.stdin.write(shot))await once(decoder.stdin,'drain');if(i%60===0)console.log(`Rendered ${i}/${frames}`)}
  const audit=await page.evaluate(()=>({frames:window.__auditCount,pixelFrames:window.__auditCount,errors:window.__auditErrors}));if(audit.frames!==frames||audit.errors.length)throw Error('Frame audit failed: '+JSON.stringify(audit));if(args.auditoutput)fs.writeFileSync(args.auditoutput,JSON.stringify(audit));
  decoder.stdin.end();const [dc]=await once(decoder,'close');const [ec]=await once(encoder,'close');if(dc||ec)throw Error(`FFmpeg failed: decoder=${dc} encoder=${ec}`);console.log(`Rendered ${frames} frames to ${args.output}`);
 }
}finally{await browser?.close();server.close()}
