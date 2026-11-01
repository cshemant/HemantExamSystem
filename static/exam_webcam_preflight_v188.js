/* V191: strictly verified webcam preflight. Only successful server validation can advance. */
(()=>{
'use strict';
const panel=document.getElementById('v188-camera-setup');if(!panel)return;
const id=Number(panel.dataset.examId),nonce=panel.dataset.nonce;
const button=document.getElementById('v188-test'),consent=document.getElementById('v188-consent');
const status=document.getElementById('v188-state'),video=document.getElementById('v188-preview');
const next=document.getElementById('v188-next'),help=document.getElementById('v188-camera-help');
let stream=null,working=false,verified=false;

// Never expose the Continue link before a verified server response.
function showNext(allowed,url){
  next.hidden=!allowed;
  next.setAttribute('aria-disabled',allowed?'false':'true');
  next.tabIndex=allowed?0:-1;
  if(allowed&&url)next.href=url;
}
showNext(false);
next.addEventListener('click',event=>{if(!verified){event.preventDefault();showNext(false);}});
function setStatus(message){status.textContent=message;}
function setHelp(message){help.textContent=message;help.hidden=!message;}
function cleanup(){
  if(stream){stream.getTracks().forEach(track=>track.stop());stream=null;}
  video.srcObject=null;video.hidden=true;
}
function cameraError(error){
  const name=error?.name||'';
  if(name==='NotAllowedError'||name==='PermissionDeniedError'||name==='SecurityError'){
    setHelp('Chrome has blocked webcam access. Open the site-controls icon beside the address, select Site settings, set Camera to Allow, then reload and retry. Also check Windows Settings → Privacy & security → Camera if access is disabled for desktop apps.');
    return 'Camera permission denied. The exam cannot begin until access is allowed.';
  }
  if(name==='NotFoundError'||name==='DevicesNotFoundError')return 'No webcam was found. Connect a camera and retry.';
  if(name==='NotReadableError'||name==='TrackStartError')return 'Webcam is unavailable or already being used by another application. Close other camera apps and retry.';
  if(name==='OverconstrainedError')return 'The camera cannot provide the requested video format. Try another webcam.';
  if(name==='AbortError')return 'The camera stopped unexpectedly. Reconnect it and retry.';
  return error?.message||'Camera verification failed. Please retry or contact your invigilator.';
}
async function awaitFrame(){
  for(let i=0;i<40;i++){
    if(video.videoWidth>=64&&video.videoHeight>=64&&stream?.getVideoTracks()[0]?.readyState==='live')return;
    await new Promise(resolve=>setTimeout(resolve,100));
  }
  throw Error('Camera preview did not become ready. Please retry.');
}
function safeNextURL(input){
  const url=new URL(input||panel.dataset.nextUrl,window.location.href);
  if(url.origin!==window.location.origin)throw Error('The exam verification destination was not valid.');
  return url.href;
}
async function run(){
  if(working||verified||!consent.checked)return;
  working=true;button.disabled=true;setHelp('');showNext(false);
  try{
    if(!window.isSecureContext||!navigator.mediaDevices?.getUserMedia)throw Error('Camera access requires HTTPS or localhost and a supported browser.');
    setStatus('Requesting webcam permission from Chrome…');
    stream=await navigator.mediaDevices.getUserMedia({audio:false,video:{width:{ideal:320},height:{ideal:240},facingMode:'user'}});
    const track=stream.getVideoTracks()[0];
    if(!track||track.readyState!=='live')throw Error('Webcam did not start.');
    video.srcObject=stream;video.hidden=false;
    await video.play();await awaitFrame();
    const canvas=document.createElement('canvas');canvas.width=320;canvas.height=240;
    const ctx=canvas.getContext('2d',{alpha:false});
    if(!ctx)throw Error('Browser cannot capture a camera test frame.');
    ctx.drawImage(video,0,0,320,240);
    const frame=canvas.toDataURL('image/jpeg',0.55);canvas.width=canvas.height=0;
    if(frame.length>108000)throw Error('Camera test image was too large. Please retry.');
    setStatus('Camera opened. Validating your test frame with the exam server…');
    const response=await fetch(panel.dataset.submitUrl,{
      method:'POST',credentials:'same-origin',cache:'no-store',
      headers:{'Content-Type':'application/json','X-CSRF-Token':document.querySelector('meta[name="csrf-token"]')?.content||''},
      body:JSON.stringify({exam_id:id,nonce,frame})
    });
    const data=await response.json().catch(()=>({}));
    if(!response.ok||data.ok!==true){
      throw Error(data.error||`Camera server validation failed (HTTP ${response.status}). Please contact your invigilator.`);
    }
    if(track.readyState!=='live')throw Error('Webcam disconnected before verification completed. Please retry.');
    const destination=safeNextURL(data.next_url);
    verified=true;consent.disabled=true;button.disabled=true;button.hidden=true;
    try{sessionStorage.setItem('exam-webcam-consent-'+id,'yes');}catch(_ignore){}
    setStatus(data.face_visible?'Camera verified successfully. Opening exam verification…':'Webcam connection verified. Please keep your face visible during the exam. Opening verification…');
    showNext(true,destination);
    // Browser permission was granted AND the server accepted the frame.
    // Navigation starts only now, never on mere consent or a failed camera test.
    window.location.assign(destination);
  }catch(error){
    verified=false;showNext(false);
    try{sessionStorage.removeItem('exam-webcam-consent-'+id);}catch(_ignore){}
    setStatus(cameraError(error));
  }finally{
    cleanup();working=false;
    if(!verified)button.disabled=!consent.checked;
  }
}
consent.addEventListener('change',()=>{button.disabled=!consent.checked||working||verified;});
button.addEventListener('click',()=>{void run();});
window.addEventListener('pagehide',cleanup,{once:true});
})();
