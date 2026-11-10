/* V189 – strict webcam and verified samples. Frame analysis is server-side.
 * Periodic frame checks are not saved. Faculty may request clearly notified video clips. */
(()=>{
'use strict';
const panel=document.getElementById('webcam-proctor-panel');if(!panel)return;
const id=Number(panel.dataset.examId), frameUrl=panel.dataset.frameUrl, statusUrl=panel.dataset.statusUrl, leaseUrl=panel.dataset.leaseUrl, nextUrl=panel.dataset.nextUrl;
const recordingControlUrl=panel.dataset.recordControlUrl, recordingChunkUrl=panel.dataset.recordChunkUrl, recordingFinishUrl=panel.dataset.recordFinishUrl;
const recordingNotice=document.getElementById('webcam-video-notice');
const video=document.getElementById('proctor-preview'), status=document.getElementById('proctor-status');
const retry=document.getElementById('v189-camera-retry');
const lock=document.getElementById('v189-camera-lock'), lockMsg=document.getElementById('v189-camera-lock-msg');
let stream=null,interval=null,lastOk=0,starting=false,uploading=false,ended=false,deviceHalted=false;
const haltMode=panel.dataset.deviceResponse==='halt';
let recordingPoll=null, recorder=null, recordingId=null, recordingIndex=0, chunkQueue=Promise.resolve(), recordingError=false;
let recordingFinishPending=null, endingExamRecording=false;
const csrf=()=>document.querySelector('meta[name="csrf-token"]')?.content||'';
const message=s=>{status.textContent=s;if(lockMsg)lockMsg.textContent=s;};
const block=s=>{if(lock)lock.style.display='flex';if(s)message(s);};
const unblock=()=>{if(!deviceHalted&&lock)lock.style.display='none';};
function deviceHold(text){deviceHalted=true;window.__deviceHold=true;block(text||'Exam halted after a possible device detection. Wait for faculty review.');if(lock){const heading=lock.querySelector('h2');if(heading)heading.textContent='Exam paused for faculty review';}if(retry)retry.style.display='none';}
async function post(url,payload){
 const r=await fetch(url,{method:'POST',credentials:'same-origin',cache:'no-store',headers:{'Content-Type':'application/json','X-CSRF-Token':csrf()},body:JSON.stringify({exam_id:id,...payload})});
 const body=await r.json().catch(()=>({}));if(!r.ok)throw Object.assign(Error(body.error||'Monitoring server unavailable'),{httpStatus:r.status});return body;
}
async function verifiedLease(){try{const r=await fetch(leaseUrl,{credentials:'same-origin',cache:'no-store'});const data=await r.json();if(data.halted){deviceHold(data.notice);return false;}if(deviceHalted&&!data.halted&&r.ok){location.reload();return false;}return r.ok&&data.ready===true;}catch(_){return false;}}
function cameraLive(){return !!(stream&&stream.getVideoTracks()[0]&&stream.getVideoTracks()[0].readyState==='live'&&video.videoWidth>=64);}
function videoNotice(text){
 if(!recordingNotice)return;
 // Hide only the routine no-recording message; preserve active-recording and error notices.
 const routine=!text||text==='Camera required · Face-count checks · No video stored';
 recordingNotice.textContent=routine?'':text;
 recordingNotice.style.display=routine?'none':'block';
 const active=text.startsWith('● Video recording');
 recordingNotice.style.color=active?'#b91c1c':'';
 recordingNotice.style.fontWeight=active?'700':'';
}
function stop(){
 ended=true;
 if(interval){clearInterval(interval);interval=null;}
 if(recordingPoll){clearInterval(recordingPoll);recordingPoll=null;}
 stopRecording();
 if(stream){stream.getTracks().forEach(t=>t.stop());stream=null;}
 video.srcObject=null;
}
async function uploadRecordedChunk(blob,clipId,index){
 const form=new FormData();form.append('exam_id',String(id));form.append('recording_id',String(clipId));form.append('index',String(index));form.append('chunk',blob,'segment.webm');
 const response=await fetch(recordingChunkUrl,{method:'POST',credentials:'same-origin',cache:'no-store',headers:{'X-CSRF-Token':csrf()},body:form});
 if(!response.ok)throw Error(`Recording upload failed: ${response.status}`);
}
function stopRecording(){
 if(!recorder)return recordingFinishPending || Promise.resolve(true);
 const active=recorder;recorder=null;
 if(active.state!=='inactive'){
  try{active.stop();}catch(_){recordingError=true;}
 }
 return recordingFinishPending || Promise.resolve(false);
}
function startRecording(clipId){
 if(ended||endingExamRecording||!cameraLive()||recorder||recordingFinishPending||typeof MediaRecorder==='undefined')return;
 const mime=['video/webm;codecs=vp8','video/webm'].find(type=>MediaRecorder.isTypeSupported(type));
 if(!mime){videoNotice('Video capture unavailable on this browser · notify invigilator');return;}
 recordingId=clipId;recordingIndex=0;recordingError=false;chunkQueue=Promise.resolve();
 let active;
 try{active=new MediaRecorder(stream,{mimeType:mime,videoBitsPerSecond:280000});}
 catch(e){videoNotice('Video recording could not start · notify invigilator');return;}
 recorder=active;
 let done;
 const finalizing=new Promise(resolve=>{done=resolve;});
 recordingFinishPending=finalizing;
 active.addEventListener('dataavailable',event=>{
   if(!event.data||!event.data.size)return;
   const index=recordingIndex++;
   chunkQueue=chunkQueue.then(()=>uploadRecordedChunk(event.data,clipId,index)).catch(()=>{
     recordingError=true;
     videoNotice('Video upload interrupted · notify invigilator');
   });
 });
 active.addEventListener('stop',()=>{
   chunkQueue.then(()=>post(recordingFinishUrl,{recording_id:clipId,client_ok:!recordingError}))
    .then(result=>{
      if(result.saved)videoNotice('Video recording stopped · clip saved for faculty review');
      else videoNotice('Video recording incomplete · notify invigilator');
      done(result.saved===true);
    })
    .catch(()=>{
      videoNotice('Video recording upload incomplete · notify invigilator');
      done(false);
    }).finally(()=>{
      if(recordingFinishPending===finalizing)recordingFinishPending=null;
    });
 });
 active.start(8000);  // uploads bounded WebM chunks; the existing camera track stays live
 videoNotice('● Video recording in progress · faculty enabled');
}
let recordingStatusPending=false;
async function checkRecordingRequest(){
 if(ended||endingExamRecording||recordingStatusPending||!recordingControlUrl||!cameraLive())return;
 recordingStatusPending=true;
 try{
  const url=new URL(recordingControlUrl,location.origin);url.searchParams.set('exam_id',String(id));
  const response=await fetch(url,{cache:'no-store',credentials:'same-origin'});
  if(!response.ok)throw Error('Recording control unavailable');
  const state=await response.json();
  if(state.record&&state.recording_id&&(!recorder||recordingId!==state.recording_id)){
   if(recorder)await stopRecording();
   else if(recordingFinishPending)await recordingFinishPending;
   if(!endingExamRecording)startRecording(state.recording_id);
  }else if(!state.record&&recorder){
   stopRecording();
   videoNotice('Video recording stopped · saving clip');
  }else if(!state.record&&!recorder&&!recordingFinishPending){
   videoNotice(state.recording_status==='saved'?'Video recording stopped · clip retained for faculty review':'Camera required · Face-count checks · No video stored');
  }
 }catch(e){
  // Network interruptions do not turn video recording on; preserve local capture state.
  if(!recorder)videoNotice('Camera required · Face-count checks · Recording status unavailable');
 }finally{recordingStatusPending=false;}
}
// Called by the existing exam submission code BEFORE leaving the exam page.
// Preserve the current MediaStream; finish uploading the final MediaRecorder data.
window.__finishExamRecording=async (timeoutMs=10000)=>{
 endingExamRecording=true;
 if(recordingPoll){clearInterval(recordingPoll);recordingPoll=null;}
 if(!recorder && !recordingFinishPending)return true;
 const pending=stopRecording();
 return Promise.race([
  pending,
  new Promise(resolve=>setTimeout(()=>resolve(false),Math.max(1000,timeoutMs)))
 ]);
};

function scheduleRecordingControl(){
 if(recordingPoll)clearInterval(recordingPoll);
 recordingPoll=setInterval(()=>{void checkRecordingRequest();},6000);
 void checkRecordingRequest();
}

async function report(name){try{await post(statusUrl,{status:name});}catch(_){}}
async function frame(){
 if(ended)return false;
 if(uploading)return false;
 if(!cameraLive()){block('Webcam is disconnected. Reconnect to continue.');return false;}
 uploading=true;
 try{
  const canvas=document.createElement('canvas');
  const width=640,height=480; // Higher-resolution evidence for small, visible phones.
  canvas.width=width;canvas.height=height;
  canvas.getContext('2d',{alpha:false}).drawImage(video,0,0,width,height);
  let image=canvas.toDataURL('image/jpeg',0.60);
  if(image.length>165000)image=canvas.toDataURL('image/jpeg',0.43);
  if(image.length>165000)image=canvas.toDataURL('image/jpeg',0.30);
  canvas.width=canvas.height=0;
  if(image.length>165000)throw Error('Camera image too large');
  try{const result=await post(frameUrl,{frame:image});if(result.halted){deviceHold(result.notice);lastOk=Date.now();return true;}}
  catch(e){if(e.httpStatus!==429||!await verifiedLease())throw e;}
  lastOk=Date.now();unblock();message('Camera active');if(nextUrl){location.replace(nextUrl);}return true;
 }catch(e){
  // One late monitoring response is not a camera disconnection. The server still
  // enforces its fresh-sample lease independently of this display.
  if(deviceHalted){return false;}
  if(lastOk&&Date.now()-lastOk<45000&&cameraLive()){
   status.textContent='Checking webcam connection…';
  }else{block('Monitoring connection failed. Reconnect camera or contact your invigilator.');}
  return false;
 }finally{uploading=false;}
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
function scheduleSamples(){
 if(interval)clearInterval(interval);
 interval=setInterval(()=>{
  if(ended)return;
  if(deviceHalted){void verifiedLease();return;}
  if(!cameraLive()||(lastOk&&Date.now()-lastOk>52000))block('Camera validation expired. Please reconnect.');
  void frame();
 },haltMode?8000:13000);
}
async function start(){
 if(starting||ended)return;starting=true;
 // Retry should verify the existing stream, never close a healthy camera.
 if(cameraLive()){
  try{if(await frame())scheduleSamples();}finally{starting=false;}
  return;
 }
 block('Connecting to webcam…');
 if(stream){stream.getTracks().forEach(t=>t.stop());stream=null;}
 try{
  if(!window.isSecureContext||!navigator.mediaDevices?.getUserMedia)throw Error('Webcam requires localhost or HTTPS.');
  await permissionBegin();
  try{stream=await navigator.mediaDevices.getUserMedia({audio:false,video:{width:{ideal:640},height:{ideal:480},facingMode:'user'}});}
  finally{permissionEnd();}
  const track=stream.getVideoTracks()[0];if(!track||track.readyState!=='live')throw Error('Camera unavailable');
  track.addEventListener('ended',()=>{if(ended)return;stopRecording();block('Webcam disconnected. Click Retry Camera.');void report('camera_interrupted');});
  video.srcObject=stream;video.style.display='block';await video.play();
  for(let n=0;n<40&&!cameraLive();n++)await new Promise(r=>setTimeout(r,100));
  if(!cameraLive())throw Error('Camera preview unavailable');
  if(!await frame())throw Error('Server rejected the camera sample');
  scheduleSamples();scheduleRecordingControl();
 }catch(e){block(e.message||'Camera unavailable. Ask invigilator for assistance.');void report(e.name==='NotAllowedError'?'permission_denied':'camera_unavailable');}
 finally{starting=false;}
}

// The existing question-navigation asset was not referenced by the provided
// exam template. Load that existing asset once; no extra source file is needed.
// It swaps only the question column, keeping the MediaStream and timers alive.
if(document.querySelector('.webcam-exam-questions') &&
   !document.querySelector('script[src*="exam_webcam_seamless_v193.js"]')){
 const source=document.currentScript?.src||'/static/exam_proctor_v189.js';
 const script=document.createElement('script');
 script.src=new URL('exam_webcam_seamless_v193.js',source).href;
 script.async=false;
 document.head.appendChild(script);
}
// Used only when a server redirect says the camera lease needs refreshing.
// This reuses the active stream and never invokes getUserMedia unnecessarily.
window.__examProctorVerifyNow=async()=>{
 if(!cameraLive()||ended){block('Webcam disconnected. Please reconnect.');return false;}
 if(uploading){return await verifiedLease();}
 return await frame();
};
retry?.addEventListener('click',()=>void start());
window.addEventListener('pagehide',stop,{once:true});
document.addEventListener('visibilitychange',()=>{if(!document.hidden&&Date.now()-lastOk>52000)block('Camera connection needs verification.');});
// V188 preflight already collected consent; keep this gate active regardless of sessionStorage.
block('Starting camera monitoring…');void start();
})();
