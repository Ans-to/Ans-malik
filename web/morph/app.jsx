import React,{useEffect,useLayoutEffect,useRef} from 'react';
import {createRoot} from 'react-dom/client';
import {Player} from '@remotion/player';
import {AbsoluteFill,useCurrentFrame} from 'remotion';
import {gsap} from 'gsap';
import * as THREE from 'three';
import './style.css';
const data=await (await fetch('/__data')).json(), words=data.words, beats=data.beats, duration=data.frames/60;
const ref=React.createRef();
function Globe({frame}){
 const el=useRef(),state=useRef();
 useEffect(()=>{const renderer=new THREE.WebGLRenderer({alpha:true,antialias:true});renderer.setSize(800,800);renderer.setPixelRatio(1);renderer.setClearColor(0,0);el.current.appendChild(renderer.domElement);
 const scene=new THREE.Scene(),camera=new THREE.PerspectiveCamera(35,1,.1,100);camera.position.z=8;
 scene.add(new THREE.AmbientLight(0xbfbaff,1.8));const light=new THREE.DirectionalLight(0xffffff,3);light.position.set(2,4,8);scene.add(light);
 const group=new THREE.Group();group.add(new THREE.Mesh(new THREE.SphereGeometry(1.7,42,32),new THREE.MeshStandardMaterial({color:0x424c8b,metalness:.46,roughness:.32})));
 group.add(new THREE.LineSegments(new THREE.WireframeGeometry(new THREE.SphereGeometry(1.71,18,12)),new THREE.LineBasicMaterial({color:0x9b90ed,transparent:true,opacity:.24})));
 const coords=[[.3,.9,1.4],[-1.1,.7,1.1],[1.2,-.5,1.1],[-.6,-1.1,1.1],[.8,.1,1.5]];
 const material=new THREE.MeshBasicMaterial({color:0xffca70});coords.forEach(p=>{let n=new THREE.Mesh(new THREE.SphereGeometry(.065,12,12),material);n.position.set(...p);group.add(n)});
 for(let i=0;i<coords.length-1;i++){let a=new THREE.Vector3(...coords[i]),b=new THREE.Vector3(...coords[i+1]);let c=a.clone().add(b).normalize().multiplyScalar(2.6);let curve=new THREE.QuadraticBezierCurve3(a,c,b);group.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(curve.getPoints(50)),new THREE.LineBasicMaterial({color:0xf6b46d})));}
 scene.add(group);state.current={renderer,scene,camera,group};return()=>{renderer.dispose();el.current?.replaceChildren()}},[]);
 useLayoutEffect(()=>{let s=state.current;if(s){s.group.rotation.y=frame*.006;s.group.rotation.x=.15+Math.sin(frame*.01)*.08;s.renderer.render(s.scene,s.camera)}},[frame]);return <div className="globe" ref={el}/>;
}
function Composition(){const frame=useCurrentFrame(),t=frame/60;const active=words.find(w=>w.start_ms<=t*1000&&w.end_ms>t*1000);const beat=[...beats].reverse().find(b=>b.start<=t)||beats[0];const current=beat?.words||[];
 useLayoutEffect(()=>{gsap.globalTimeline.clear();const tl=gsap.timeline({defaults:{ease:'power2.inOut'}});
 tl.fromTo('.actor',{width:1120,height:154,borderRadius:80,scale:.75,rotationX:15,opacity:0},{scale:1,rotationX:0,opacity:1,duration:.6,ease:'back.out(1.7)'},0);
 const starts=beats.map(b=>b.start);const at=i=>starts[Math.min(i,starts.length-1)]||0;
 tl.to('.actor',{width:750,height:960,borderRadius:8,rotationX:8,rotationY:-8,duration:.7},at(1)-.18)
 .to('.prompt',{opacity:0,duration:.3},at(1)-.18).to('.paper',{opacity:1,duration:.35},at(1)-.05)
 .fromTo('.marker',{strokeDashoffset:850},{strokeDashoffset:0,duration:.65},(words.find(w=>/predict/i.test(w.word))?.start_ms||1400)/1000)
 .to('.actor',{width:1420,height:650,borderRadius:45,rotationY:0,rotationX:0,duration:.7},at(2)-.18)
 .to('.paper',{opacity:0,duration:.35},at(2)-.12).to('.chart-layer',{opacity:1,duration:.3},at(2)-.05)
 .fromTo('.bridge',{opacity:0},{opacity:1,duration:.12},at(2)-.22)
 .fromTo('.bridge-path',{attr:{d:'M 765 570 Q 950 580 1140 570'}},{attr:{d:'M 240 720 C450 690 490 670 600 560 S840 580 970 440 S1220 470 1550 250'},duration:.75},at(2)-.18)
 .to('.bridge',{opacity:0,duration:.2},at(2)+.55)
 .fromTo('.chart-path',{strokeDashoffset:1700},{strokeDashoffset:0,duration:.7},at(2))
 .fromTo('.portal',{scale:.02,opacity:0,x:620,y:-215},{scale:1.6,opacity:1,x:0,y:0,duration:.62},at(3)-.2)
 .to('.chart-layer',{opacity:0,duration:.3},at(3)+.2).to('.portal',{scale:2.3,duration:.8},at(3)+.12)
 .to('.portal',{scale:.12,x:-390,y:-120,duration:.5},at(4)-.18)
 .to('.actor',{width:1420,height:640,borderRadius:40,rotationY:0,duration:.65},at(4)-.18)
 .to('.bento',{opacity:1,duration:.4},at(4)).fromTo('.bento-card',{scale:.3,opacity:0,rotationY:75},{scale:1,opacity:1,rotationY:0,duration:.45,stagger:.08,ease:'back.out(1.7)'},at(4))
 .to('.actor',{rotationY:180,width:1250,height:600,duration:.65},at(5)-.15)
 .to('.bento',{opacity:0,duration:.25},at(5)).to('.kinetic',{opacity:1,duration:.35},at(5)+.12);
 // Every later beat reshapes the same continuous object; no scene switch.
 for(let i=6;i<beats.length;i++){let a=at(i)-.16;tl.to('.actor',{width:i%2?1370:1080,height:i%2?520:690,borderRadius:i%2?280:48,rotationY:180+(i%2?10:-10),rotationX:i%2?7:-5,duration:.62},a)
 .to('.orb',{scale:i%2?1.8:.7,x:i%2?280:-280,y:i%2?-90:80,duration:.7},a)
 .fromTo('.kinetic-word',{scale:.58,opacity:.4,z:-180},{scale:1,opacity:1,z:0,duration:.5,stagger:.045,ease:'back.out(1.7)'},a+.1)}
 gsap.globalTimeline.pause();window.__gsap=gsap;return()=>tl.kill()},[]);
 const typed=Math.min(26,Math.floor(t*29));let last=active?.word||'';return <AbsoluteFill className="world"><div className="grid"/><div className="wash"/><div className="header"><span>THE ANSWER ENGINE / A CLOSER LOOK</span><span>CONTINUOUS MOTION STUDY ↗</span></div>
 <div className="camera" style={{transform:`perspective(1200px) translateZ(${Math.min(90,t*7)}px) rotate(${Math.sin(t*.55)*.45}deg)`}}><div className="actor">
 <div className="prompt"><span className="spark">✳</span><span>{'Why does AI get it wrong?'.slice(0,typed)}<i className="cursor"/></span><b>↗</b></div>
 <div className="paper"><img src={'/'+data.document}/><svg viewBox="0 0 760 980" preserveAspectRatio="none"><path className="marker" d="M78 395 Q360 404 650 393" fill="none" stroke="#ffda63" strokeWidth="44" strokeLinecap="round" strokeDasharray="850" strokeDashoffset="850"/></svg></div>
 <div className="chart-layer"><div className="chart-caption">FROM <em>LANGUAGE</em> TO EVIDENCE</div><svg viewBox="0 0 1400 650"><defs><linearGradient id="fill" x2="0" y2="1"><stop stopColor="#9d89ff" stopOpacity=".28"/><stop offset="1" stopColor="#9d89ff" stopOpacity="0"/></linearGradient></defs><path d="M40 570 C250 540 290 520 400 410 S640 430 770 290 S1020 320 1350 100 L1350 650 L40 650Z" fill="url(#fill)"/><path className="chart-path" d="M40 570 C250 540 290 520 400 410 S640 430 770 290 S1020 320 1350 100" fill="none" stroke="#f6c568" strokeWidth="9" strokeLinecap="round" strokeDasharray="1700" strokeDashoffset="1700"/><circle cx="1350" cy="100" r="17" fill="#fff1c4"/></svg><small>ILLUSTRATIVE MOTION GRAPHIC · NOT MEASURED DATA</small></div>
 <div className="portal"><Globe frame={frame}/><span className="target-node"/></div>
 <div className="bento"><div className="bento-card"><small>SOURCE CHECK</small><strong>Look <em>closer.</em></strong><p>A polished answer isn't proof.</p><div className="bars"><i/><i/></div></div><div className="bento-card"><small>THE SIGNAL</small><strong>COMPARE</strong><p>Claims with evidence.</p><span className="counter">{String(Math.floor((t*37)%100)).padStart(2,'0')} <sup>illustrative</sup></span></div><div className="bento-card"><small>BETTER HABIT</small><strong>VERIFY ↗</strong><p>Before you trust.</p><span className="icon">✳</span></div></div>
 <div className="kinetic"><div className="orb"/><div className="kinetic-label">THE TAKEAWAY / WORD BY WORD</div><div className="kinetic-words" key={beat?.index}>{current.map((w,i)=><span className={'kinetic-word '+(active?.word===w?'current':'')} key={i}>{w}</span>)}</div></div>
 </div></div><svg className="bridge" viewBox="0 0 1920 1080"><path className="bridge-path" d="M 765 570 Q 950 580 1140 570" fill="none" stroke="#ffcf64" strokeWidth="9" strokeLinecap="round"/></svg><div className="caption"><span>●</span><div>{words.filter(w=>beat?.word_ids.includes(w.word_id)).map((w,i)=><span className={active===w?'on':''} key={w.word_id}>{w.word} </span>)}</div></div><div className="foot">EVIDENCE FIRST <span> / </span> {String((beat?.index||0)+1).padStart(2,'0')}</div></AbsoluteFill>
}
createRoot(document.getElementById('root')).render(<Player ref={ref} component={Composition} durationInFrames={data.frames} fps={60} compositionWidth={1920} compositionHeight={1080} style={{width:'100vw',height:'100vh'}} controls={false} autoPlay={false}/>);
window.renderFrame=async(frame)=>{ref.current.seekTo(frame);await new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)));window.__gsap.globalTimeline.seek(frame/60,false);await new Promise(r=>requestAnimationFrame(r))};
await document.fonts.ready;while(!ref.current||!window.__gsap)await new Promise(r=>setTimeout(r,10));window.ready=true;
