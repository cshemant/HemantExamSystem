(function(){
  const root=document.getElementById('student-code-editor');if(!root)return;
  const language=document.getElementById('code-language'),source=document.getElementById('code-source'),stdin=document.getElementById('code-stdin');
  const output=document.getElementById('code-output'),status=document.getElementById('code-status'),run=document.getElementById('code-run');
  const lineNumbers=document.getElementById('code-line-numbers'),bracketLayer=document.getElementById('code-bracket-layer');
  const examples={
    c:'#include <stdio.h>\n\nint main() {\n    printf("Hello, World!\\n");\n    return 0;\n}\n',
    cpp:'#include <iostream>\nusing namespace std;\n\nint main() {\n    cout << "Hello, World!" << endl;\n    return 0;\n}\n',
    java:'public class Main {\n    public static void main(String[] args) {\n        System.out.println("Hello, World!");\n    }\n}\n',
    python:'print("Hello, World!")\n',
    php:'<?php\necho "Hello, World!\\n";\n?>\n'
  };
  const drafts={};
  function escapeHtml(value){return value.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}
  function bracketAtCaret(){
    const value=source.value,caret=source.selectionStart;
    if('()[]{}'.includes(value.charAt(caret)))return caret;
    if(caret>0&&'()[]{}'.includes(value.charAt(caret-1)))return caret-1;
    return -1;
  }
  function matchingBracket(index){
    if(index<0)return -1;
    const value=source.value,pairs={'(':')','[':']','{':'}',')':'(',']':'[','}':'{'};
    const bracket=value.charAt(index),mate=pairs[bracket];if(!mate)return -1;
    const forward='([{'.includes(bracket),step=forward?1:-1;let depth=0;
    for(let i=index;i>=0&&i<value.length;i+=step){
      const current=value.charAt(i);
      if(current===bracket)depth+=1;
      else if(current===mate){depth-=1;if(depth===0)return i;}
    }
    return -1;
  }
  function renderEditorGuides(){
    const value=source.value,count=Math.max(1,value.split('\n').length);
    lineNumbers.textContent=Array.from({length:count},(_,index)=>index+1).join('\n');
    const active=bracketAtCaret(),matching=matchingBracket(active);
    if(active>=0){
      const marked=new Set([active]);if(matching>=0)marked.add(matching);
      let html='';
      for(let i=0;i<value.length;i++){
        const character=escapeHtml(value.charAt(i));
        html+=marked.has(i)?'<mark class="code-matching-bracket">'+character+'</mark>':character;
      }
      bracketLayer.innerHTML=html+(value.endsWith('\n')?' ':'');
    }else bracketLayer.textContent=value+(value.endsWith('\n')?' ':'');
    lineNumbers.scrollTop=source.scrollTop;
    bracketLayer.scrollTop=source.scrollTop;bracketLayer.scrollLeft=source.scrollLeft;
  }
  function load(lang){source.value=drafts[lang]===undefined?examples[lang]:drafts[lang];output.textContent='Run your program to see the output here.';output.className='';status.textContent='Ready';renderEditorGuides();}
  let active=language.value;load(active);
  language.addEventListener('change',()=>{drafts[active]=source.value;active=language.value;load(active);source.focus();});
  source.addEventListener('keydown',event=>{if(event.key==='Tab'){event.preventDefault();const a=source.selectionStart,b=source.selectionEnd;source.setRangeText('    ',a,b,'end');renderEditorGuides();}});
  source.addEventListener('input',renderEditorGuides);
  source.addEventListener('click',renderEditorGuides);
  source.addEventListener('keyup',renderEditorGuides);
  source.addEventListener('select',renderEditorGuides);
  source.addEventListener('scroll',renderEditorGuides);
  document.getElementById('code-reset').addEventListener('click',()=>{if(!confirm('Reset this language to the starter code?'))return;drafts[active]=examples[active];source.value=examples[active];stdin.value='';output.textContent='Run your program to see the output here.';output.className='';status.textContent='Ready';renderEditorGuides();});
  document.getElementById('code-clear').addEventListener('click',()=>{output.textContent='';output.className='';});
  function wait(ms){return new Promise(resolve=>setTimeout(resolve,ms));}
  async function readJob(url){
    const started=Date.now();let checks=0;
    while(Date.now()-started<5*60*1000){
      // Jittered 3.5–5 second checks avoid synchronized classroom bursts.
      // Even 50 waiting students produce only about 10–14 lightweight status
      // reads per second, while compilation stays outside Gunicorn.
      await wait(3500+Math.floor(Math.random()*1500));
      const response=await fetch(url,{headers:{'Accept':'application/json'},cache:'no-store'});
      const result=await response.json().catch(()=>({ok:false,error:'The server returned an invalid response.'}));
      if(!response.ok||!result.ok)throw new Error(result.error||'Unable to check the program status.');
      if(result.status==='completed'||result.status==='failed')return result;
      checks+=1;
      if(result.status==='queued'){
        const position=result.position||1;status.textContent='Queued · '+position+' ahead';output.textContent='Waiting safely in the classroom queue (position '+position+').';
      }else{status.textContent='Running…';output.textContent='Compiling and running in the isolated code service…';}
      if(checks>20)await wait(2500);
    }
    throw new Error('The program is still queued. Please select Run again later.');
  }
  run.addEventListener('click',async()=>{
    if(!source.value.trim()){output.textContent='Write some code before selecting Run.';output.className='code-output-error';return;}
    run.disabled=true;status.textContent='Running…';output.textContent='Compiling and running…';output.className='';
    try{
      const response=await fetch(root.dataset.runUrl,{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':document.querySelector('meta[name="csrf-token"]').content},body:JSON.stringify({language:language.value,source:source.value,stdin:stdin.value})});
      const result=await response.json().catch(()=>({ok:false,error:'The server returned an invalid response.'}));
      if(!response.ok||!result.ok)throw new Error(result.error||'Code execution failed.');
      status.textContent='Queued · '+(result.position||1);output.textContent='Program accepted. Waiting safely in the classroom queue…';
      const completed=await readJob(result.status_url);
      if(completed.status==='failed')throw new Error(completed.error||'Code execution failed.');
      output.textContent=completed.output;output.className=completed.success?'code-output-success':'code-output-error';status.textContent=completed.exit_code===null||completed.exit_code===undefined?'Finished':'Exit code '+completed.exit_code;
    }catch(error){output.textContent=error.message||'Code execution failed.';output.className='code-output-error';status.textContent='Failed';}
    finally{run.disabled=false;}
  });
})();
