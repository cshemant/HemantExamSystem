(function(){
  const csrf=()=>{const meta=document.querySelector('meta[name="csrf-token"]');return meta?meta.content:'';};
  function initTheoryClass(){
    const experimentSelect=document.getElementById('theory-experiment-select');
    if(experimentSelect){experimentSelect.addEventListener('change',()=>{const base=experimentSelect.getAttribute('data-register-url');window.location=`${base}?experiment_id=${encodeURIComponent(experimentSelect.value)}`;});}
    const search=document.getElementById('theory-student-search');
    if(search){search.addEventListener('input',()=>{const q=(search.value||'').trim().toLowerCase();document.querySelectorAll('[data-theory-row]').forEach(row=>{row.hidden=Boolean(q)&&!(row.getAttribute('data-student-search')||'').includes(q);});});}
    const form=document.querySelector('[data-theory-entry]');if(!form)return;
    const endpoint=form.getAttribute('data-save-url');
    const saveRow=async(row)=>{
      const input=row.querySelector('[data-theory-date]');const state=row.querySelector('[data-theory-status]');if(!input||!state)return;
      state.textContent='Saving…';state.className='practical-save-state saving';
      try{
        const res=await fetch(endpoint,{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':csrf()},body:JSON.stringify({student_id:Number(row.getAttribute('data-student-id')),experiment_id:Number(row.getAttribute('data-experiment-id')),performed_date:input.value})});
        const data=await res.json();if(!res.ok||!data.ok)throw new Error(data.error||'Save failed');
        state.textContent=data.performed_date?'Saved':'—';state.className=`practical-save-state${data.performed_date?' saved':''}`;
      }catch(err){state.textContent='Retry';state.title=err.message||'Save failed';state.className='practical-save-state error';}
    };
    form.querySelectorAll('[data-theory-row]').forEach(row=>{const input=row.querySelector('[data-theory-date]');if(input)input.addEventListener('change',()=>saveRow(row));});
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',initTheoryClass);else initTheoryClass();
})();
