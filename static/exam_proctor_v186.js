/* V186 — Opt-in exam webcam samples, no snapshots retained in browser or server.
   Requires a camera-supported HTTPS context and an explicit first-time student action.
   It does not identify people, enforce exam termination, or prove misconduct. */
(function(){
  'use strict';
  const panel=document.getElementById('webcam-proctor-panel');
  if(!panel)return;
  const examId=Number(panel.dataset.examId), frameUrl=panel.dataset.frameUrl, statusUrl=panel.dataset.statusUrl;
  const consent=document.getElementById('proctor-consent');
  const button=document.getElementById('proctor-start');
  const status=document.getElementById('proctor-status');
  const video=document.getElementById('proctor-preview');
  const consentKey='exam-webcam-consent-'+examId;
  let stream=null, timer=null, uploading=false, stopped=false, cameraStarting=false;
  const csrf=()=>document.querySelector('meta[name="csrf-token"]')?.content||'';
  const setStatus=text=>{ if(status)status.textContent=text; };
  async function send(url,payload){
    const response=await fetch(url,{method:'POST',credentials:'same-origin',cache:'no-store',
      headers:{'Content-Type':'application/json','X-CSRF-Token':csrf()},body:JSON.stringify({exam_id:examId,...payload})});
    if(!response.ok)throw new Error('HTTP '+response.status);
    return response.json();
  }
  async function reportProblem(eventName){
    try{await send(statusUrl,{status:eventName});}catch(_error){}
  }
  function stop(){
    stopped=true;
    if(timer){clearInterval(timer);timer=null;}
    if(stream){for(const track of stream.getTracks())track.stop();stream=null;}
    if(video)video.srcObject=null;
  }
  async function capture(){
    if(stopped||uploading||!stream||document.hidden||!video.videoWidth)return;
    uploading=true;
    try{
      const canvas=document.createElement('canvas');canvas.width=320;canvas.height=240;
      canvas.getContext('2d',{alpha:false}).drawImage(video,0,0,320,240);
      const frame=canvas.toDataURL('image/jpeg',0.55);
      canvas.width=0;canvas.height=0;
      if(frame.length>108000){setStatus('Image too large; ask invigilator for help.');return;}
      await send(frameUrl,{frame});
      setStatus('Camera active · sampled for faculty review');
    }catch(e){
      setStatus('Camera monitoring connection problem · inform invigilator');
    }finally{uploading=false;}
  }
  // In the secure PIN/fullscreen shell, give the parent a chance to mark
  // the browser-native camera permission transition BEFORE getUserMedia starts.
  async function cameraPermissionBegin(){
    if(window.parent===window){
      window.dispatchEvent(new Event('exam-camera-permission-start'));
      return;
    }
    await new Promise(resolve=>{
      let settled=false;
      const finish=()=>{
        if(settled)return;
        settled=true;
        window.removeEventListener('message',onAck);
        resolve();
      };
      const onAck=e=>{
        if(e.origin===window.location.origin && e.source===window.parent &&
           e.data?.type==='exam-camera-permission-ack' && Number(e.data.exam_id)===examId)finish();
      };
      window.addEventListener('message',onAck);
      window.parent.postMessage({type:'exam-camera-permission-start',exam_id:examId},window.location.origin);
      setTimeout(finish,750);
    });
  }
  function cameraPermissionEnd(){
    if(window.parent===window)window.dispatchEvent(new Event('exam-camera-permission-end'));
    else window.parent.postMessage({type:'exam-camera-permission-end',exam_id:examId},window.location.origin);
  }
  async function start(){
    if(cameraStarting||stream||stopped)return;
    cameraStarting=true;button.disabled=true;setStatus('Requesting camera permission…');
    if(!window.isSecureContext||!navigator.mediaDevices||!navigator.mediaDevices.getUserMedia){
      setStatus('Webcam requires HTTPS and a supported browser. Inform invigilator.');
      await reportProblem('camera_unavailable');cameraStarting=false;return;
    }
    await cameraPermissionBegin();
    try{
      stream=await navigator.mediaDevices.getUserMedia({audio:false,video:{width:{ideal:320},height:{ideal:240},facingMode:'user'}});
      video.srcObject=stream;video.style.display='block';
      await video.play();
      sessionStorage.setItem(consentKey,'yes');
      stream.getVideoTracks()[0]?.addEventListener('ended',()=>{
        if(stopped)return;
        setStatus('Camera disconnected · inform invigilator');
        void reportProblem('camera_interrupted');
        if(timer)clearInterval(timer);
      });
      setStatus('Webcam active · monitoring started');
      // If first frame is delayed by camera startup, the next 25-second sample still runs.
      setTimeout(()=>{void capture();},1400);
      timer=setInterval(()=>{void capture();},25000);
    }catch(err){
      setStatus('Webcam not available ('+(err && err.name ? err.name : 'error')+'). Contact invigilator.');
      await reportProblem(err && err.name==='NotAllowedError'?'permission_denied':'camera_unavailable');
      sessionStorage.removeItem(consentKey);
      button.disabled=false;
    }finally{
      cameraPermissionEnd();
      cameraStarting=false;
    }
  }
  consent.addEventListener('change',()=>{button.disabled=!consent.checked||!!stream;});
  button.addEventListener('click',()=>{if(consent.checked)void start();});
  // Consent continues for question-to-question navigations in the same tab.
  if(sessionStorage.getItem(consentKey)==='yes'){
    consent.checked=true;
    button.disabled=false;
    void start();
  }
  window.addEventListener('pagehide',stop,{once:true});
})();
