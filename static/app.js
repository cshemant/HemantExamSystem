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


function initDesktopNavDropdowns(){
  const dropdowns=[...document.querySelectorAll('.nav-dropdown')];
  if(!dropdowns.length) return;
  document.addEventListener('click',event=>{
    dropdowns.forEach(dropdown=>{
      if(dropdown.open && !dropdown.contains(event.target)) dropdown.open=false;
    });
  });
  document.addEventListener('keydown',event=>{
    if(event.key==='Escape'){
      dropdowns.forEach(dropdown=>{dropdown.open=false;});
    }
  });
  dropdowns.forEach(dropdown=>{
    dropdown.querySelectorAll('a').forEach(link=>link.addEventListener('click',()=>{dropdown.open=false;}));
  });
}
if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',initDesktopNavDropdowns); else initDesktopNavDropdowns();

function initCopyButtons(){
  document.querySelectorAll('[data-copy-target]').forEach(btn=>{
    btn.addEventListener('click',async()=>{
      const target=document.getElementById(btn.getAttribute('data-copy-target'));
      if(!target)return;
      try{await navigator.clipboard.writeText((target.textContent||'').trim());const old=btn.textContent;btn.textContent='Copied';setTimeout(()=>btn.textContent=old,1200);}catch(_err){}
    });
  });
}
if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',initCopyButtons); else initCopyButtons();

function initExamCentreNetworkRefresh(){
  const btn=document.getElementById('refresh-network-btn');
  if(!btn) return;
  const endpoint=btn.getAttribute('data-network-url');
  const urlEl=document.getElementById('student-access-url');
  const ipEl=document.getElementById('lan-ip-value');
  const portEl=document.getElementById('lan-port-value');
  const qrEl=document.getElementById('student-qr-code');
  const openEl=document.getElementById('open-student-login');
  const statusEl=document.getElementById('network-refresh-status');
  let refreshing=false;

  const setStatus=(text,isError=false)=>{
    if(!statusEl) return;
    statusEl.textContent=text;
    statusEl.classList.toggle('network-refresh-error',Boolean(isError));
  };

  const refreshNetwork=async(manual=false)=>{
    if(refreshing) return;
    refreshing=true;
    const oldText=btn.textContent;
    if(manual){btn.disabled=true;btn.textContent='Refreshing…';setStatus('Checking the current LAN connection…');}
    try{
      const res=await fetch(`${endpoint}?_=${Date.now()}`,{method:'GET',cache:'no-store',headers:{'Accept':'application/json'}});
      if(!res.ok) throw new Error('Network refresh failed');
      const data=await res.json();
      const previous=urlEl ? (urlEl.textContent||'').trim() : '';
      if(urlEl) urlEl.textContent=data.student_url;
      if(ipEl) ipEl.textContent=data.lan_ip;
      if(portEl) portEl.textContent=data.port;
      if(qrEl) qrEl.src=data.qr_uri;
      if(openEl) openEl.href=data.student_url;
      const changed=previous && previous!==data.student_url;
      if(manual || changed){
        setStatus(changed ? `Network changed. Student URL and QR code updated to ${data.student_url}.` : `Network checked. Current student URL is ${data.student_url}.`);
      }
    }catch(_err){
      if(manual) setStatus('Could not refresh the LAN address. Check the laptop network connection and try again.',true);
    }finally{
      refreshing=false;
      if(manual){btn.disabled=false;btn.textContent=oldText;}
    }
  };

  btn.addEventListener('click',()=>refreshNetwork(true));
  // Re-check periodically so a Wi-Fi/LAN/hotspot change is reflected without a page reload.
  setInterval(()=>refreshNetwork(false),15000);
}
if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',initExamCentreNetworkRefresh); else initExamCentreNetworkRefresh();

function initQuestionBankSubjectCatalog(){
  const subject=document.getElementById('bank-subject-select');
  const course=document.getElementById('bank-course-semester');
  if(!subject || !course) return;
  let autoFilled='';
  const applyDefault=()=>{
    const option=subject.options[subject.selectedIndex];
    if(!option) return;
    const next=(option.getAttribute('data-course')||'').trim();
    const current=(course.value||'').trim();
    if(!current || current===autoFilled){
      course.value=next;
      autoFilled=next;
    }
  };
  subject.addEventListener('change',applyDefault);
  if(!(course.value||'').trim()) applyDefault();
}
if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',initQuestionBankSubjectCatalog); else initQuestionBankSubjectCatalog();

function saveMultiAnswer(examId, questionId, fieldName){
  const values=[...document.querySelectorAll(`input[name="${fieldName}"]:checked`)].map(el=>el.value);
  return saveAnswer(examId,questionId,values.join(','));
}

const freeAnswerTimers=new Map();
function initFreeAnswerAutosave(){
  document.querySelectorAll('[data-autosave-question]').forEach(input=>{
    input.addEventListener('input',()=>{
      const examId=Number(input.getAttribute('data-autosave-exam'));
      const questionId=Number(input.getAttribute('data-autosave-question'));
      const key=`${examId}:${questionId}`;
      clearTimeout(freeAnswerTimers.get(key));
      freeAnswerTimers.set(key,setTimeout(()=>saveAnswer(examId,questionId,input.value),450));
    });
    input.addEventListener('blur',()=>{
      const examId=Number(input.getAttribute('data-autosave-exam'));
      const questionId=Number(input.getAttribute('data-autosave-question'));
      saveAnswer(examId,questionId,input.value);
    });
  });
}
if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',initFreeAnswerAutosave); else initFreeAnswerAutosave();

function startExamHeartbeat(examId,seconds=15){
  const interval=Math.max(10,Math.min(60,Number(seconds)||15))*1000;
  const ping=async(state='active')=>{
    try{await fetch('/student/heartbeat',{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':csrfToken()},body:JSON.stringify({exam_id:examId,state})});}catch(_err){}
  };
  ping();setInterval(()=>ping(document.hidden?'hidden':'active'),interval);
  window.addEventListener('online',()=>ping('online'));
  window.addEventListener('offline',()=>ping('offline'));
}

function initQuestionTypeForms(){
  document.querySelectorAll('[data-question-definition-form]').forEach(form=>{
    const selector=form.querySelector('[data-question-type-selector]');
    if(!selector)return;
    const update=()=>{
      const type=selector.value;
      form.querySelectorAll('[data-qtype-section]').forEach(section=>{
        const key=section.getAttribute('data-qtype-section');
        const show=key===type || (key==='choice' && ['single_choice','multiple_select'].includes(type));
        section.hidden=!show;
        section.querySelectorAll('input,select,textarea').forEach(el=>{el.disabled=!show;});
      });
    };
    selector.addEventListener('change',update);update();
  });
}
if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',initQuestionTypeForms); else initQuestionTypeForms();

function initExamInteractionMonitoring(){
  const form=document.querySelector('[data-exam-integrity]');
  if(!form)return;
  const examId=Number(form.getAttribute('data-exam-integrity'));
  form.addEventListener('copy',()=>logIntegrity(examId,'copy_attempt','Copy action used in exam form'));
  form.addEventListener('paste',()=>logIntegrity(examId,'paste_attempt','Paste action used in exam form'));
  form.addEventListener('contextmenu',()=>logIntegrity(examId,'context_menu','Context menu opened in exam form'));
}
if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',initExamInteractionMonitoring); else initExamInteractionMonitoring();

function formatRemaining(total){
  const seconds=Math.max(0,Number(total)||0),m=Math.floor(seconds/60),s=seconds%60;
  return `${m}m ${s}s`;
}
function initLiveExamMonitor(){
  const card=document.querySelector('[data-live-monitor-url]');
  if(!card)return;
  const endpoint=card.getAttribute('data-live-monitor-url');
  const body=document.getElementById('live-candidate-body');
  const esc=value=>String(value??'').replace(/[&<>"]/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[ch]));
  const refresh=async()=>{
    try{
      const res=await fetch(`${endpoint}?_=${Date.now()}`,{cache:'no-store',headers:{Accept:'application/json'}});if(!res.ok)return;
      const data=await res.json();
      const set=(id,val)=>{const el=document.getElementById(id);if(el)el.textContent=val;};
      set('live-online',data.counts.online);set('live-stale',data.counts.stale);set('live-offline',data.counts.offline);set('live-online-count',data.counts.online);
      if(!body)return;
      if(!data.rows.length){body.innerHTML='<tr><td colspan="7">No examination is currently in progress.</td></tr>';return;}
      body.innerHTML=data.rows.map(r=>{
        const cls=r.connection==='online'?'success':(r.connection==='stale'?'warning':'gray');
        return `<tr><td><strong>${esc(r.roll_no)}</strong><div class="mini-meta">${esc(r.name)}</div></td><td>${esc(r.exam)}</td><td><span class="badge ${cls}">${esc(r.connection.charAt(0).toUpperCase()+r.connection.slice(1))}</span></td><td>${esc(r.answers)}</td><td>${esc(r.integrity)}</td><td>${formatRemaining(r.remaining_seconds)}</td><td>${esc(r.last_seen||'-')}</td></tr>`;
      }).join('');
    }catch(_err){}
  };
  setInterval(refresh,5000);
}
if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',initLiveExamMonitor); else initLiveExamMonitor();

function initQuestionBankSelectAll(){
  document.querySelectorAll('[data-select-all]').forEach(master=>{
    master.addEventListener('change',()=>{
      const name=master.getAttribute('data-select-all');
      document.querySelectorAll(`input[name="${name}"]:not(:disabled)`).forEach(box=>{box.checked=master.checked;});
    });
  });
}
if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',initQuestionBankSelectAll); else initQuestionBankSelectAll();

function initPracticeBuilder(){
  const subject=document.getElementById('practice-subject');
  const unit=document.getElementById('practice-unit');
  if(!subject || !unit) return;
  const updateUnits=()=>{
    const opt=subject.options[subject.selectedIndex];
    let units=[];
    try{units=JSON.parse(opt?.getAttribute('data-units')||'[]');}catch(_err){units=[];}
    unit.innerHTML='<option value="">All units</option>'+units.map(v=>`<option value="${String(v).replace(/"/g,'&quot;')}">Unit ${String(v).replace(/</g,'&lt;')}</option>`).join('');
  };
  subject.addEventListener('change',updateUnits);updateUnits();
}
if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',initPracticeBuilder); else initPracticeBuilder();

function practiceFieldValue(fieldName,qtype){
  if(qtype==='multiple_select') return [...document.querySelectorAll(`input[name="${fieldName}"]:checked`)].map(el=>el.value).join(',');
  const checked=document.querySelector(`input[name="${fieldName}"]:checked`);
  if(checked) return checked.value;
  const input=document.querySelector(`[name="${fieldName}"]`);
  return input ? input.value : '';
}

function initPracticeFeedback(){
  document.querySelectorAll('[data-practice-check]').forEach(btn=>{
    btn.addEventListener('click',async()=>{
      const feedback=document.getElementById(btn.getAttribute('data-feedback-id'));
      const answer=practiceFieldValue(btn.getAttribute('data-field-name'),btn.getAttribute('data-question-type'));
      if(!answer){if(feedback){feedback.hidden=false;feedback.className='practice-feedback error';feedback.textContent='Choose or enter an answer first.';}return;}
      btn.disabled=true;const old=btn.textContent;btn.textContent='Checking…';
      try{
        const res=await fetch('/student/practice/check-answer',{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':csrfToken()},body:JSON.stringify({attempt_id:Number(btn.getAttribute('data-attempt-id')),ref_key:btn.getAttribute('data-ref-key'),answer})});
        const data=await res.json();
        if(!res.ok) throw new Error(data.error||'Could not check answer');
        if(feedback){feedback.hidden=false;feedback.className=`practice-feedback ${data.correct?'correct':'incorrect'}`;feedback.innerHTML=`<strong>${data.correct?'Correct':'Not correct'}</strong><div>${data.correct?'':`Correct answer: ${escapeHtml(data.correct_answer)}<br>`}${escapeHtml(data.explanation)}</div>`;}
      }catch(err){if(feedback){feedback.hidden=false;feedback.className='practice-feedback error';feedback.textContent=err.message||'Could not check answer.';}}
      finally{btn.disabled=false;btn.textContent=old;}
    });
  });
}
function escapeHtml(value){return String(value??'').replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));}
if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',initPracticeFeedback); else initPracticeFeedback();

function initPracticeTimer(){
  const form=document.querySelector('[data-practice-end-epoch]');
  const display=document.getElementById('practice-timer-value');
  if(!form || !display) return;
  const end=Number(form.getAttribute('data-practice-end-epoch'))*1000;
  let submitted=false;
  const tick=()=>{
    const remaining=Math.max(0,Math.floor((end-Date.now())/1000));
    const m=Math.floor(remaining/60),s=remaining%60;display.textContent=`${m}:${String(s).padStart(2,'0')}`;
    if(remaining<=60) display.classList.add('urgent');
    if(remaining<=0 && !submitted){submitted=true;display.textContent='0:00';form.requestSubmit();return;}
    if(!submitted)setTimeout(tick,1000);
  };
  form.addEventListener('submit',()=>{submitted=true;});tick();
}
if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',initPracticeTimer); else initPracticeTimer();

function initPracticalMarks(){
  const form=document.querySelector('[data-practical-entry]');
  const experimentSelect=document.getElementById('practical-experiment-select');
  if(experimentSelect){
    experimentSelect.addEventListener('change',()=>{
      const base=experimentSelect.getAttribute('data-register-url');
      window.location=`${base}?experiment_id=${encodeURIComponent(experimentSelect.value)}`;
    });
  }
  const search=document.getElementById('practical-student-search');
  if(search){search.addEventListener('input',()=>{const q=(search.value||'').trim().toLowerCase();document.querySelectorAll('[data-practical-row]').forEach(row=>{row.hidden=Boolean(q)&&!(row.getAttribute('data-student-search')||'').includes(q);});});}
  if(!form)return;
  const endpoint=form.getAttribute('data-save-url');
  const rows=[...form.querySelectorAll('[data-practical-row]')];
  const components=row=>[...row.querySelectorAll('[data-practical-component]')];
  const updateTotal=row=>{
    const total=row.querySelector('[data-practical-total]');if(!total)return;
    const inputs=components(row);const hasValue=inputs.some(input=>input.value!=='');
    if(!hasValue){return;}
    const sum=inputs.reduce((acc,input)=>acc+(Number.parseFloat(input.value)||0),0);
    total.value=Number.isInteger(sum)?String(sum):sum.toFixed(1).replace(/\.0$/,'');
  };
  const saveRow=async(row)=>{
    const attendance=row.querySelector('[data-practical-attendance]');const remarks=row.querySelector('[data-practical-remarks]');const state=row.querySelector('[data-practical-status]');const inputs=components(row);
    if(!attendance||!state)return;
    const payload={student_id:Number(row.getAttribute('data-student-id')),experiment_id:Number(row.getAttribute('data-experiment-id')),attendance:attendance.value,remarks:remarks?remarks.value:''};
    inputs.forEach(input=>{payload[input.getAttribute('data-practical-component-key')]=input.value;});
    state.textContent='Saving…';state.className='practical-save-state saving';
    try{
      const res=await fetch(endpoint,{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':csrfToken()},body:JSON.stringify(payload)});
      const data=await res.json();if(!res.ok||!data.ok)throw new Error(data.error||'Save failed');
      const total=row.querySelector('[data-practical-total]');if(total)total.value=(data.total===null||data.total===undefined)?'':data.total;
      state.textContent='Saved';state.className='practical-save-state saved';
    }catch(err){state.textContent='Retry';state.title=err.message||'Save failed';state.className='practical-save-state error';}
  };
  rows.forEach((row,index)=>{
    const attendance=row.querySelector('[data-practical-attendance]');const inputs=components(row);
    const syncAttendance=()=>{
      const attendanceInput=row.querySelector('[data-practical-component-key="attendance_marks"]');
      const gradedInputs=inputs.filter(input=>input!==attendanceInput);
      const attendanceMax=attendanceInput?Number.parseFloat(attendanceInput.max||'0')||0:0;
      if(attendance.value==='A'){
        if(attendanceInput){attendanceInput.disabled=false;attendanceInput.value='0';}
        gradedInputs.forEach(input=>{input.value='';input.disabled=true;});
        const total=row.querySelector('[data-practical-total]');if(total)total.value='0';
      }else{
        gradedInputs.forEach(input=>{input.disabled=false;});
        if(attendanceInput)attendanceInput.disabled=false;
        if(!attendance.value&&gradedInputs.some(input=>input.value!==''))attendance.value='P';
        if(attendance.value==='P'&&attendanceInput)attendanceInput.value=String(attendanceMax);
        else if(!attendance.value&&attendanceInput)attendanceInput.value='';
        updateTotal(row);
      }
    };
    syncAttendance();
    attendance.addEventListener('change',()=>{syncAttendance();saveRow(row);});
    inputs.forEach(input=>{
      input.addEventListener('input',()=>{syncAttendance();updateTotal(row);});
      input.addEventListener('change',()=>{syncAttendance();saveRow(row);});
      input.addEventListener('keydown',event=>{
        if(event.key==='Enter'){
          event.preventDefault();saveRow(row);
          const key=input.getAttribute('data-practical-component-key');
          const next=rows.slice(index+1).find(r=>!r.hidden);const nextInput=next&&next.querySelector(`[data-practical-component-key="${key}"]`);
          if(nextInput&&!nextInput.disabled){nextInput.focus();nextInput.select();}
        }
      });
    });
  });
}
if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',initPracticalMarks); else initPracticalMarks();
