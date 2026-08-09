function csrfToken(){
  const el=document.querySelector('meta[name="csrf-token"]');
  return el ? el.getAttribute('content') : '';
}
async function saveAnswer(examId, questionId, answer, retryCount=0){
  const status=document.getElementById('save-status');
  if(status) status.textContent='Saving…';
  try{
    const res=await fetch('/student/save-answer',{
      method:'POST',
      headers:{'Content-Type':'application/json','X-CSRF-Token':csrfToken()},
      body:JSON.stringify({exam_id:examId,question_id:questionId,answer:answer})
    });
    const data=await res.json();
    if(!res.ok) throw new Error(data.error || 'Save failed');
    if(data.submitted){window.location='/student/submitted/'+examId;return;}
    if(status){status.textContent='Saved';setTimeout(()=>{if(status.textContent==='Saved')status.textContent='';},1000);}
  }catch(err){
    if(status) status.textContent='Save failed — retrying…';
    if(retryCount<10) setTimeout(()=>saveAnswer(examId,questionId,answer,retryCount+1),3000);
  }
}
function startTimer(endEpoch){
  const timer=document.getElementById('timer');
  const form=document.getElementById('exam-form');
  let handle=null;
  const tick=()=>{
    const left=Math.max(0,Math.floor(endEpoch-Date.now()/1000));
    const h=Math.floor(left/3600),m=Math.floor((left%3600)/60),s=left%60;
    if(timer) timer.textContent=`${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`;
    if(left<=0){if(handle)clearInterval(handle);if(form)form.submit();}
  };
  tick();handle=setInterval(tick,1000);
}
async function logIntegrity(examId,eventType,details=''){
  try{
    const res=await fetch('/student/integrity-event',{
      method:'POST',
      headers:{'Content-Type':'application/json','X-CSRF-Token':csrfToken()},
      body:JSON.stringify({exam_id:examId,event_type:eventType,details:details})
    });
    if(!res.ok) return null;
    return await res.json();
  }catch(_err){return null;}
}
function startIntegrity(examId,requireFullscreen,tabLimit){
  let enteredFullscreen=false;
  let tabEvents=0;
  const banner=document.getElementById('integrity-warning');
  const fullscreenBtn=document.getElementById('fullscreen-btn');
  const updateBanner=()=>{
    if(!banner) return;
    if(tabEvents>0){
      const threshold=tabLimit>0 ? ` / ${tabLimit}` : '';
      banner.textContent=`Integrity monitoring: ${tabEvents}${threshold} tab/full-screen event(s) recorded. Stay on the exam screen.`;
      banner.classList.add('active');
    }
  };
  document.addEventListener('visibilitychange',async()=>{
    if(document.hidden){tabEvents+=1;await logIntegrity(examId,'tab_hidden','Exam tab became hidden');updateBanner();}
  });
  if(requireFullscreen){
    if(fullscreenBtn){fullscreenBtn.addEventListener('click',async()=>{
      try{await document.documentElement.requestFullscreen();enteredFullscreen=true;fullscreenBtn.textContent='Full Screen Active';}
      catch(_err){fullscreenBtn.textContent='Full Screen Unavailable';}
    });}
    document.addEventListener('fullscreenchange',async()=>{
      if(document.fullscreenElement){enteredFullscreen=true;if(fullscreenBtn)fullscreenBtn.textContent='Full Screen Active';return;}
      if(enteredFullscreen){tabEvents+=1;await logIntegrity(examId,'fullscreen_exit','Full-screen mode exited');updateBanner();if(fullscreenBtn)fullscreenBtn.textContent='Re-enter Full Screen';}
    });
  }
}

function initMobileMenu(){
  const toggle=document.querySelector('.mobile-menu-toggle');
  const menu=document.getElementById('mobile-menu');
  if(!toggle || !menu) return;
  const closeButtons=menu.querySelectorAll('[data-mobile-menu-close]');
  const panel=menu.querySelector('.mobile-menu-panel');
  const openMenu=()=>{
    menu.classList.add('is-open');
    menu.setAttribute('aria-hidden','false');
    toggle.setAttribute('aria-expanded','true');
    document.body.classList.add('mobile-menu-open');
    const first=menu.querySelector('.mobile-menu-links a');
    if(first) setTimeout(()=>first.focus(),40);
  };
  const closeMenu=()=>{
    menu.classList.remove('is-open');
    menu.setAttribute('aria-hidden','true');
    toggle.setAttribute('aria-expanded','false');
    document.body.classList.remove('mobile-menu-open');
  };
  toggle.addEventListener('click',()=>menu.classList.contains('is-open')?closeMenu():openMenu());
  closeButtons.forEach(btn=>btn.addEventListener('click',closeMenu));
  menu.querySelectorAll('a').forEach(link=>link.addEventListener('click',closeMenu));
  document.addEventListener('keydown',event=>{if(event.key==='Escape' && menu.classList.contains('is-open')) closeMenu();});
  if(panel) panel.addEventListener('click',event=>event.stopPropagation());
}
if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',initMobileMenu); else initMobileMenu();
