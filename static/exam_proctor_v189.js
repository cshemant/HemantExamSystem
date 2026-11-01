/* V189 – strict webcam and verified samples. Frame analysis is server-side.
 * No frame persistence. Do not trust a browser-only flag for enforcement. */
(()=>{
'use strict';
const panel=document.getElementById('webcam-proctor-panel');if(!panel)return;
const id=Number(panel.dataset.examId), frameUrl=panel.dataset.frameUrl, statusUrl=panel.dataset.statusUrl, leaseUrl=panel.dataset.leaseUrl, nextUrl=panel.dataset.nextUrl;
const video=document.getElementById('proctor-preview'), status=document.getElementById('proctor-status');
const retry=document.getElementById('v189-camera-retry'), legacyRetry=document.getElementById('proctor-start');
const lock=document.getElementById('v189-camera-lock'), lockMsg=document.getElementById('v189-camera-lock-msg');
let stream=null,interval=null,lastOk=0,starting=false,uploading=false,ended=false;
const csrf=()=>document.querySelector('meta[name="csrf-token"]')?.content||'';
const message=s=>{status.textContent=s;if(lockMsg)lockMsg.textContent=s;};
const block=s=>{if(lock)lock.style.display='flex';if(s)message(s);};
const unblock=()=>{if(lock)lock.style.display='none';};
async function post(url,payload){
 const r=await fetch(url,{method:'POST',credentials:'same-origin',cache:'no-store',headers:{'Content-Type':'application/json','X-CSRF-Token':csrf()},body:JSON.stringify({exam_id:id,...payload})});
 const body=await r.json().catch(()=>({}));if(!r.ok)throw Object.assign(Error(body.error||'Monitoring server unavailable'),{httpStatus:r.status});return body;
}
async function verifiedLease(){try{const r=await fetch(leaseUrl,{credentials:'same-origin',cache:'no-store'});const data=await r.json();return r.ok&&data.ready===true;}catch(_){return false;}}
function cameraLive(){return !!(stream&&stream.getVideoTracks()[0]&&stream.getVideoTracks()[0].readyState==='live'&&video.videoWidth>=64);}
function stop(){ended=true;if(interval){clearInterval(interval);interval=null;}if(stream){stream.getTracks().forEach(t=>t.stop());stream=null;}video.srcObject=null;}
async function report(name){try{await post(statusUrl,{status:name});}catch(_){}}
async function frame(){
 if(ended||uploading||!cameraLive()){block('Webcam is disconnected. Reconnect to continue.');return false;}
 uploading=true;
 try{
  const canvas=document.createElement('canvas');canvas.width=320;canvas.height=240;
  canvas.getContext('2d',{alpha:false}).drawImage(video,0,0,320,240);
  const image=canvas.toDataURL('image/jpeg',0.55);canvas.width=canvas.height=0;
  if(image.length>108000)throw Error('Camera image too large');
  try{await post(frameUrl,{frame:image});}
  catch(e){if(e.httpStatus!==429||!await verifiedLease())throw e;}
  lastOk=Date.now();unblock();message('Camera active · monitoring samples are being verified');if(nextUrl){location.replace(nextUrl);}return true;
 }catch(e){block('Monitoring connection failed. Reconnect camera or contact your invigilator.');return false;}
 finally{uploading=false;}
}
async function permissionBegin(){
 if(window.parent===window){window.dispatchEvent(new Event('exam-camera-permission-start'));return;}
 await new Promise(resolve=>{
  let done=false;const finish=()=>{if(done)return;done=true;window.removeEventListener('message',ack);resolve();};
  function ack(event){if(event.source===window.parent&&event.origin===location.origin&&event.data?.type==='exam-camera-permission-ack'&&Number(event.data.exam_id)===id)finish();}
  window.addEventListener('message',ack);
  window.parent.postMessage({type:'exam-camera-permission-start',exam_id:id},location.origin);
  setTimeout(finish,800);
 });
}
function permissionEnd(){if(window.parent===window)window.dispatchEvent(new Event('exam-camera-permission-end'));else window.parent.postMessage({type:'exam-camera-permission-end',exam_id:id},location.origin);}
async function start(){
 if(starting||ended)return;starting=true;block('Connecting to webcam…');
 if(stream){stream.getTracks().forEach(t=>t.stop());stream=null;}
 try{
  if(!window.isSecureContext||!navigator.mediaDevices?.getUserMedia)throw Error('Webcam requires localhost or HTTPS.');
  await permissionBegin();
  try{stream=await navigator.mediaDevices.getUserMedia({audio:false,video:{width:{ideal:320},height:{ideal:240},facingMode:'user'}});}
  finally{permissionEnd();}
  const track=stream.getVideoTracks()[0];if(!track||track.readyState!=='live')throw Error('Camera unavailable');
  track.addEventListener('ended',()=>{if(ended)return;block('Webcam disconnected. Click Retry Camera.');void report('camera_interrupted');});
  video.srcObject=stream;video.style.display='block';await video.play();
  for(let n=0;n<40&&!cameraLive();n++)await new Promise(r=>setTimeout(r,100));
  if(!cameraLive())throw Error('Camera preview unavailable');
  if(!await frame())throw Error('Server rejected the camera sample');
  if(interval)clearInterval(interval);
  interval=setInterval(()=>{if(ended)return;if(!cameraLive()||Date.now()-lastOk>52000){block('Camera validation expired. Please reconnect.');}void frame();},20000);
 }catch(e){block(e.message||'Camera unavailable. Ask invigilator for assistance.');void report(e.name==='NotAllowedError'?'permission_denied':'camera_unavailable');}
 finally{starting=false;}
}
retry?.addEventListener('click',()=>void start());legacyRetry?.addEventListener('click',()=>void start());
window.addEventListener('pagehide',stop,{once:true});
document.addEventListener('visibilitychange',()=>{if(!document.hidden&&Date.now()-lastOk>52000)block('Camera connection needs verification.');});
// V188 preflight already collected consent; keep this gate active regardless of sessionStorage.
block('Starting camera monitoring…');void start();
})();
