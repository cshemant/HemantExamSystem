/* V193 — Keep the running webcam stream alive while changing exam questions.
 * Only intercept normal Next / Previous question POSTs. Server still validates
 * position, minimum view time, camera lease, CSRF and exam expiry. */
(()=>{
  'use strict';
  const panel=document.getElementById('webcam-proctor-panel');
  const column=document.querySelector('.webcam-exam-questions');
  if(!panel||!column||!document.getElementById('exam-form'))return;
  const examId=Number(panel.dataset.examId);
  if(!Number.isInteger(examId)||examId<1)return;
  let pending=false;
  const allowedActions=new Set([
    `/student/exam/${examId}/next-question`,
    `/student/exam/${examId}/previous-question`
  ]);
  function csrf(){return document.querySelector('meta[name="csrf-token"]')?.content||'';}
  function statusMessage(value){
    const node=document.getElementById('save-status');
    if(node){node.textContent=value;node.setAttribute('aria-live','polite');}
  }
  function cameraBlocked(message){
    const lock=document.getElementById('v189-camera-lock');
    const text=document.getElementById('v189-camera-lock-msg');
    if(text)text.textContent=message||'Camera verification required. Reconnect your camera.';
    if(lock)lock.style.display='flex';
  }
  function bindInsertedControls(){
    // app.js attaches these handlers once to the original form on DOMContentLoaded.
    // Reattach only to the newly inserted elements; never restart the webcam,
    // exam timer, integrity listeners, or heartbeat timers.
    if(typeof window.initFreeAnswerAutosave==='function')window.initFreeAnswerAutosave();
    if(typeof window.initExamSubmitConfirmation==='function')window.initExamSubmitConfirmation();
    if(typeof window.initSingleFlightExamNavigation==='function')window.initSingleFlightExamNavigation();
    if(typeof window.initExamInteractionMonitoring==='function')window.initExamInteractionMonitoring();
    if(typeof window.startSequentialNextCountdown==='function')window.startSequentialNextCountdown();
  }
  function swapQuestion(documentFromServer){
    const latest=documentFromServer.querySelector('.webcam-exam-questions');
    const current=document.querySelector('.webcam-exam-questions');
    const nextForm=latest?.querySelector('#exam-form');
    if(!latest||!current||!nextForm)return false;
    // Avoid changing editor scripts that need full-page initialization.
    if(latest.querySelector('.mock-code-column')||current.querySelector('.mock-code-column'))return false;
    const priorPosition=current.querySelector('input[name="expected_position"]')?.value;
    const newPosition=nextForm.querySelector('input[name="expected_position"]')?.value;
    const newBadge=documentFromServer.querySelector('.sequential-progress-badge');
    const badge=document.querySelector('.sequential-progress-badge');
    current.replaceChildren(...Array.from(latest.childNodes));
    if(badge&&newBadge)badge.textContent=newBadge.textContent;
    // Security continuity: webcam panel and JS instance remain untouched.
    bindInsertedControls();
    if(priorPosition&&newPosition&&priorPosition===newPosition){
      statusMessage('Question unchanged; follow the on-screen timing rules.');
    }else{
      statusMessage('Question loaded · webcam monitoring continues');
    }
    const heading=current.querySelector('.question-title');
    if(heading){heading.setAttribute('tabindex','-1');heading.focus({preventScroll:true});}
    return true;
  }
  document.addEventListener('submit',async event=>{
    const form=event.target;
    if(!(form instanceof HTMLFormElement)||form.id!=='exam-form')return;
    const submitter=event.submitter;
    if(!(submitter instanceof HTMLElement))return;
    const requested=submitter.getAttribute('formaction');
    if(!requested)return;
    const destination=new URL(requested,window.location.href);
    if(destination.origin!==window.location.origin||!allowedActions.has(destination.pathname))return;
    // Older technical-code-editor workflows continue to use normal navigation.
    if(form.closest('.mock-technical-layout'))return;
    event.preventDefault();
    event.stopImmediatePropagation(); // Avoid the old native-navigation handler.
    if(pending)return;
    pending=true;
    const caption=submitter.textContent;
    submitter.disabled=true;
    submitter.textContent='Loading question…';
    statusMessage('Loading question · camera remains active');
    try{
      const payload=new FormData(form);
      // Keep server-side expected_position and CSRF validation unchanged.
      const response=await fetch(destination.href,{
        method:'POST',credentials:'same-origin',cache:'no-store',redirect:'follow',
        headers:{'X-Requested-With':'XMLHttpRequest','Accept':'text/html','X-CSRF-Token':csrf()},
        body:payload
      });
      if(response.status===423){
        const error=await response.json().catch(()=>({}));
        cameraBlocked(error.error||'Camera monitoring paused. Reconnect to continue.');
        statusMessage('Camera verification required before moving on');
        return;
      }
      if(!response.ok)throw Error(`Question could not be loaded (HTTP ${response.status}).`);
      const resolved=new URL(response.url,window.location.href);
      if(resolved.origin!==window.location.origin)throw Error('Unexpected exam redirect.');
      const html=await response.text();
      const parsed=new DOMParser().parseFromString(html,'text/html');
      if(!swapQuestion(parsed)){
        // Only when the server changes workflow (expiry, section selection,
        // submission, etc.) do we allow an ordinary page navigation.
        window.location.assign(resolved.href);
        return;
      }
    }catch(error){
      statusMessage('Question change was not confirmed. Please retry or ask the invigilator.');
      // Do not automatically repeat POST: a previous request might have committed.
    }finally{
      pending=false;
      if(submitter.isConnected){submitter.disabled=false;submitter.textContent=caption;}
    }
  },true);
})();
