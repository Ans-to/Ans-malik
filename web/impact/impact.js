import * as THREE from 'three';
import {gsap} from '/node_modules/gsap/index.js';
import {FontLoader} from 'three/addons/loaders/FontLoader.js';
import {TextGeometry} from 'three/addons/geometries/TextGeometry.js';

const W=innerWidth,H=innerHeight,params=new URLSearchParams(location.search);
const r=new THREE.WebGLRenderer({antialias:true,preserveDrawingBuffer:true,powerPreference:'high-performance'});r.setSize(W,H);r.setPixelRatio(1);r.toneMapping=THREE.ACESFilmicToneMapping;document.body.prepend(r.domElement);
const cam=new THREE.PerspectiveCamera(43,W/H,.1,150);cam.position.set(0,0,12);
function lights(scene){scene.add(new THREE.AmbientLight('#ACBDCC',.7));for(const [color,intensity,pos] of [['#FFE3B8',5,[5,7,6]],['#A8C8E8',2,[-5,2,4]],['#F59E0B',9,[0,4,-6]]]){const l=new THREE.DirectionalLight(color,intensity);l.position.set(...pos);scene.add(l)}scene.fog=new THREE.FogExp2('#090B10',.018)}
const metal=new THREE.MeshStandardMaterial({color:'#C18D3D',metalness:.8,roughness:.25,emissive:'#3A2208',emissiveIntensity:.4});
const shatter=new THREE.Scene();shatter.background=new THREE.Color('#090B10');lights(shatter);
const fragments=[];let seed=4891;function rand(){seed=(seed*1664525+1013904223)>>>0;return seed/4294967296}
for(let i=0;i<144;i++){
 const geo=new THREE.TetrahedronGeometry(.08+rand()*.18,0);const mesh=new THREE.Mesh(geo,metal);
 const dir=new THREE.Vector3((rand()-.5)*2,(rand()-.5)*2,(rand()-.35)*2).normalize();
 const base=new THREE.Vector3((rand()-.5)*2.2,(rand()-.5)*2.7,(rand()-.5)*.8);
 shatter.add(mesh);fragments.push({mesh,dir,base,spin:new THREE.Vector3(rand()*8,rand()*7,rand()*9),speed:1.5+rand()*5});
}
const monolith=new THREE.Mesh(new THREE.BoxGeometry(1.8,3,.7),metal);shatter.add(monolith);
// A true extruded text mesh sits behind the typographic overlay.
const loadedFont=await new FontLoader().loadAsync('/node_modules/three/examples/fonts/helvetiker_bold.typeface.json');
const text3d=/(\bai\b|artificial intelligence|language model|chatgpt)/i.test(params.get('topic')||'')?'WRONG ANSWERS':(params.get('topic')||'THE STORY').slice(0,28).toUpperCase();
const textMesh=new THREE.Mesh(new TextGeometry(text3d,{font:loadedFont,size:.47,depth:.12,curveSegments:3,bevelEnabled:true,bevelThickness:.015,bevelSize:.012,bevelSegments:1}),metal);textMesh.position.set(-4.5,-1.15,-1);shatter.add(textMesh);
const chart=new THREE.Scene();chart.background=new THREE.Color('#2D1025');lights(chart);
const pts=[];for(let i=0;i<80;i++){const x=i*.17-6.4;pts.push(new THREE.Vector3(x,-2.7+i*.06+Math.sin(i*.24)*.32,i*.014))}
const path=new THREE.CatmullRomCurve3(pts);const tubeGeo=new THREE.TubeGeometry(path,360,.055,6,false);const tube=new THREE.Mesh(tubeGeo,new THREE.MeshStandardMaterial({color:'#F59E0B',emissive:'#D97706',emissiveIntensity:1.8,metalness:.8,roughness:.25}));chart.add(tube);
const tip=new THREE.Mesh(new THREE.SphereGeometry(.16,16,12),new THREE.MeshStandardMaterial({color:'#F3F4F6',emissive:'#F59E0B',emissiveIntensity:2,metalness:.8,roughness:.25}));chart.add(tip);
const barriers=[];for(let i=0;i<3;i++){const group=new THREE.Group();const mat=new THREE.MeshStandardMaterial({color:'#A5D8E5',metalness:.8,roughness:.25,transparent:true,opacity:.35});const slab=new THREE.Mesh(new THREE.BoxGeometry(.08,6,.5),mat);slab.position.x= -3+i*3;group.add(slab);chart.add(group);const shards=[];for(let j=0;j<32;j++){const mesh=new THREE.Mesh(new THREE.TetrahedronGeometry(.07+rand()*.13),mat);mesh.position.set(slab.position.x,(rand()-.5)*5,(rand()-.5));chart.add(mesh);shards.push({mesh,v:new THREE.Vector3(rand()*2,(rand()-.5)*5,(rand()-.5)*4),base:mesh.position.clone(),spin:rand()*5})}barriers.push({slab,shards,trigger:(i+1)/4})}
const shaderScene=new THREE.Scene(),ortho=new THREE.OrthographicCamera(-1,1,1,-1,0,2);ortho.position.z=1;
const material=new THREE.ShaderMaterial({uniforms:{uTime:{value:0},uLow:{value:0},uMid:{value:0},uHigh:{value:0},uAspect:{value:W/H}},vertexShader:`varying vec2 vUv; void main(){vUv=uv; gl_Position=vec4(position,1.0);}`,fragmentShader:`
precision highp float; varying vec2 vUv;uniform float uTime,uLow,uMid,uHigh,uAspect;
float field(vec3 p){float wave=sin(p.x*4.0+uTime*2.0)*sin(p.y*4.5-uTime*1.6)*sin(p.z*3.7+uTime)*(.10+.18*uLow);return length(p)-1.05+wave;}
vec3 norm(vec3 p){vec2 e=vec2(.003,0.);return normalize(vec3(field(p+e.xyy)-field(p-e.xyy),field(p+e.yxy)-field(p-e.yxy),field(p+e.yyx)-field(p-e.yyx)));}
void main(){vec2 p=(vUv-.5)*vec2(uAspect,1.)*2.;vec3 ro=vec3(0.,0.,-3.4),rd=normalize(vec3(p,2.));float t=0.;float hit=0.;for(int i=0;i<56;i++){vec3 q=ro+rd*t;float d=field(q);if(d<.003){hit=1.;break;}t+=d*.7;if(t>8.)break;}
vec3 bg=mix(vec3(.025,.012,.055),vec3(.13,.025,.07),vUv.y);vec3 col=bg;if(hit>0.){vec3 q=ro+rd*t,n=norm(q);float key=max(dot(n,normalize(vec3(-.4,.8,-.5))),0.);float rim=pow(1.-max(dot(n,-rd),0.),2.);float spec=pow(max(dot(reflect(rd,n),normalize(vec3(.6,.6,-1.))),0.),22.);col=vec3(.12,.08,.14)+key*vec3(.42,.21,.10)+spec*vec3(1.2,.85,.55)+rim*vec3(.95,.08,.22)*(1.+uMid);}
float ring=exp(-abs(length(p)-1.12-.08*sin(uTime*3.))*22.)*(.18+uHigh);col+=ring*vec3(.7,.07,.20);gl_FragColor=vec4(col,1.);}`});
shaderScene.add(new THREE.Mesh(new THREE.PlaneGeometry(2,2),material));
const ids=['hook','invert','dossier','chart','shader','climax'];const starts=[0,1.8,3.6,6,9,12,15];
const paper=document.querySelector('#paper'); const doc=params.get('doc');let boxes={};
if(doc){paper.src='/'+doc;try{const info=await (await fetch('/'+doc+'.json')).json();boxes=Object.fromEntries(info.boxes.map(x=>[x.word_id,x.box.map((v,i)=>v/(i%2?info.height:info.width)*100)]))}catch(e){console.error(e)}}else paper.style.display='none';
const topic=params.get('topic')||'';document.querySelector('#hook .small').textContent=topic;
if(!/(\bai\b|artificial intelligence|language model|chatgpt)/i.test(topic)){
 const title=document.querySelector('#hook .hero');title.textContent=topic;title.style.fontSize=topic.length>35?'7.5vw':'10vw';
 document.querySelector('#invert .hero').innerHTML='THE<br>STORY.';document.querySelector('#chart .hero').innerHTML='DATA.<br>CONTEXT.<br>QUESTION.';
 document.querySelector('#shader .hero').innerHTML='LOOK.<br>THINK.<br>VERIFY.';
}
function easeOutBack(t){return gsap.parseEase('back.out(1.7)')(Math.min(1,Math.max(0,t)))}
window.renderFrame=async(frameIdx,fps=60,word='',wordAge=1,levels=[0,0,0],wordId=-1,wordProgress=0)=>{
 const t=(frameIdx/fps)%15;let beat=starts.findIndex((x,i)=>i<6&&t>=x&&t<starts[i+1]);const u=t-starts[beat];
 ids.forEach((id,i)=>document.getElementById(id).classList.toggle('on',i===beat));
 const label=document.getElementById('word');label.textContent=word||'';label.classList.toggle('ink',beat===1||beat===2);label.style.transform=`translateX(-50%) scale(${1+.28*Math.exp(-Math.max(0,wordAge)*14)})`;
 if(beat===0){const k=1-Math.exp(-u*2.8);monolith.scale.setScalar(Math.max(.05,1-k*1.15));monolith.rotation.set(u*.7,u*1.1,0);for(const f of fragments){f.mesh.position.copy(f.base).addScaledVector(f.dir,k*f.speed*2.8);f.mesh.rotation.set(f.spin.x*u,f.spin.y*u,f.spin.z*u)}cam.position.set(0,0,12-2*k);cam.rotation.set(0,0,0);textMesh.rotation.y=-.15*Math.sin(u*2);r.render(shatter,cam);document.querySelector('#hook .hero').style.transform=`scale(${3.3-2.3*easeOutBack(u*fps/8)})`;}
 else if(beat===1){r.setClearColor('#F4F1EA');r.clear();document.querySelector('#invert .hero').style.transform=`scale(${3.5-2.5*easeOutBack(u*fps/9)})`;document.querySelector('#invert .red').style.translate=`${Math.max(0,100-u*fps*12)}% 0`;}
 else if(beat===2){r.setClearColor('#18181B');r.clear();document.querySelector('#beam').style.translate=`${-55+u*65}% 0`;document.querySelector('#paperwrap').style.transform=`rotate(-14deg) scale(${1.20+u*.10})`;
 const mark=document.querySelector('#mark'),box=boxes[wordId];mark.style.display=box?'block':'none';if(box){mark.style.left=box[0]+'%';mark.style.top=box[1]+'%';mark.style.width=(box[2]-box[0])+'%';mark.style.height=(box[3]-box[1])+'%';mark.style.transform=`scaleX(${Math.max(0,Math.min(1,wordProgress))})`};document.querySelector('#dossier .cut').style.scale=`${Math.max(0,1-u*4)} 1`;}
 else if(beat===3){let p=Math.min(.98,1-Math.exp(-u*1.35));p=Math.max(.02,p);const at=path.getPointAt(p);tip.position.copy(at);tubeGeo.setDrawRange(0,Math.max(6,Math.floor(tubeGeo.index.count*p/6)*6));for(const b of barriers){let e=Math.max(0,p-b.trigger);b.slab.visible=e<=0;for(const x of b.shards){x.mesh.visible=e>0;x.mesh.position.copy(x.base).addScaledVector(x.v,e*3);x.mesh.rotation.set(e*x.spin,e*x.spin*.7,e*x.spin*.4)}}cam.position.set(at.x-1,at.y+.15,9);cam.rotation.set(0,0,-.314);r.render(chart,cam);}
 else if(beat===4){material.uniforms.uTime.value=t;material.uniforms.uLow.value=levels[0]||0;material.uniforms.uMid.value=levels[1]||0;material.uniforms.uHigh.value=levels[2]||0;r.render(shaderScene,ortho);document.querySelector('#shader .fill').textContent=word||'THE MODEL';}
 else {r.setClearColor('#E11D48');r.clear();document.querySelector('#climax .hero').style.transform=`translateX(${Math.max(0,1-easeOutBack(u*fps/9))*-110}%)`;}
};
await document.fonts.ready;if(doc) await paper.decode();window.ready=true;await window.renderFrame(0);
