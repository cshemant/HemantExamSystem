/* V188: camera permission and verified sample BEFORE creating exam attempt. */
(()=>{
'use strict';
const panel=document.getElementById('v188-camera-setup'); if(!panel)return;
const id=Number(panel.dataset.examId), nonce=panel.dataset.nonce;
const button=document.getElementById('v188-test'), consent=document.getElementById('v188-consent');
const status=document.getElementById('v188-state'),video=document.getElementById('v188-preview'),next=document.getElementById('v188-next');
let stream=null,working=false,verified=false;
const setStatus=message=>{status.textContent=message;};
function cleanup(){if(stream){stream.getTracks().forEach(t=>t.stop());stream=null;}video.srcObject=null;}
async function awaitFrame(){
  for(let i=0;i<40;i++){
    if(video.videoWidth>=64 && video.videoHeight>=64 && stream?.getVideoTracks()[0]?.readyState==='live')return;
    await new Promise(resolve=>setTimeout(resolve,100));
  }
  throw Error('Camera video did not become ready. Try again.');
}
async function run(){
 if(working||verified||!consent.checked)return;working=true;button.disabled=true;
 try{
   if(!window.isSecureContext || !navigator.mediaDevices?.getUserMedia)throw Error('Camera permission requires HTTPS or localhost and a supported browser.');
   setStatus('Requesting camera permission…');
   stream=await navigator.mediaDevices.getUserMedia({audio:false,video:{width:{ideal:320},height:{ideal:240},facingMode:'user'}});
   const track=stream.getVideoTracks()[0];
   if(!track || track.readyState!=='live')throw Error('Camera stream did not start.');
   video.srcObject=stream;video.hidden=false;await video.play();await awaitFrame();
   const canvas=document.createElement('canvas');canvas.width=320;canvas.height=240;
   canvas.getContext('2d',{alpha:false}).drawImage(video,0,0,320,240);
   const frame=canvas.toDataURL('image/jpeg',0.55);canvas.width=canvas.height=0;
   if(frame.length>108000)throw Error('Camera test image is too large.');
   setStatus('Testing camera connection with the examination server…');
   const response=await fetch(panel.dataset.submitUrl,{method:'POST',credentials:'same-origin',cache:'no-store',headers:{'Content-Type':'application/json','X-CSRF-Token':document.querySelector('meta[name="csrf-token"]')?.content||''},body:JSON.stringify({exam_id:id,nonce,frame})});
   const data=await response.json().catch(()=>({}));
   if(!response.ok||!data.ok)throw Error(data.error||'Camera server connection failed.');
   if(track.readyState!=='live')throw Error('Camera disconnected. Retry.');
   try{sessionStorage.setItem('exam-webcam-consent-'+id,'yes');}catch(_storageError){}
   verified=true;button.hidden=true;consent.disabled=true;next.hidden=false;
   setStatus(data.face_visible?'Camera verified. You may continue.':'Camera connected and verified. Face was not detected in the sample; ensure your face is visible during the exam.');
 }catch(error){try{sessionStorage.removeItem('exam-webcam-consent-'+id);}catch(_storageError){}setStatus(error?.message||'Webcam unavailable. Contact your invigilator.');}
 finally{cleanup();working=false;if(!verified)button.disabled=!consent.checked;}
}
consent.addEventListener('change',()=>{button.disabled=!consent.checked||working||verified;});
button.addEventListener('click',()=>{void run();});
window.addEventListener('pagehide',cleanup,{once:true});
})();
