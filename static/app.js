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
    timer.textContent=`${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`;
    if(left<=0){if(handle)clearInterval(handle);if(form)form.submit();}
  };
  tick();handle=setInterval(tick,1000);
}
