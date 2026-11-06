import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import readline from 'node:readline';
import os from 'node:os';
import zlib from 'node:zlib';
import {spawnSync} from 'node:child_process';
import puppeteer from 'puppeteer-core';
import chromium from '@sparticuz/chromium';
const root=process.cwd();
const server=http.createServer((req,res)=>{const url=decodeURIComponent((req.url||'/').split('?')[0]);const file=path.resolve(root,'.'+url);if(!file.startsWith(root+path.sep)){res.writeHead(403);return res.end()}const ext=path.extname(file);res.setHeader('Content-Type',({'.html':'text/html','.js':'text/javascript','.ttf':'font/ttf'})[ext]||'application/octet-stream');fs.createReadStream(file).on('error',()=>{res.statusCode=404;res.end()}).pipe(res)});
await new Promise(r=>server.listen(0,'127.0.0.1',r));
const libdir=path.join(os.tmpdir(),'cinema-chrome-libs');
if (!fs.existsSync(path.join(libdir,'lib','libnspr4.so'))) { fs.mkdirSync(libdir,{recursive:true}); const archive=zlib.brotliDecompressSync(fs.readFileSync(path.join(root,'node_modules/@sparticuz/chromium/bin/al2023.tar.br'))); const result=spawnSync('tar',['-xf','-','-C',libdir],{input:archive}); if(result.status!==0) throw new Error('Unable to unpack Chromium libraries'); }
process.env.LD_LIBRARY_PATH=path.join(libdir,'lib')+(process.env.LD_LIBRARY_PATH?':'+process.env.LD_LIBRARY_PATH:'');
const browser=await puppeteer.launch({headless:true,executablePath:await chromium.executablePath(),args:['--no-sandbox','--disable-setuid-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-webgl','--ignore-gpu-blocklist']});
const page=await browser.newPage();const width=Number(process.argv[2]),height=Number(process.argv[3]);await page.setViewport({width,height,deviceScaleFactor:1});
page.on('pageerror',err=>console.error(err));
await page.goto(`http://127.0.0.1:${server.address().port}/web/impact/index.html?topic=${encodeURIComponent(process.argv[4] || "Why Your AI Gives You Wrong Answers")}&doc=${encodeURIComponent(process.argv[5] || "")}`,{waitUntil:'networkidle0'});await page.waitForFunction('window.ready === true',{timeout:30000});
console.log('READY');
for await(const line of readline.createInterface({input:process.stdin,crlfDelay:Infinity})){let request=JSON.parse(line);if(request.close)break;await page.evaluate(({frame,fps,word,wordAge,levels,wordId,wordProgress,particleData})=>window.renderFrame(frame,fps,word,wordAge,levels,wordId,wordProgress,particleData),request);const image=await page.screenshot({type:'png',encoding:'base64'});console.log(image)}
await browser.close();server.close();
