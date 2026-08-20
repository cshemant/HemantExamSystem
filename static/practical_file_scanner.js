(function(){
  'use strict';

  function ready(fn){
    if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',fn,{once:true});
    else fn();
  }

  ready(function(){
    const root=document.querySelector('[data-practical-file-scanner]');
    if(!root) return;

    const scanUrl=root.dataset.scanUrl;
    const deleteTemplate=root.dataset.deleteUrlTemplate||'';
    const csrf=(document.querySelector('meta[name="csrf-token"]')||{}).content||'';
    const camera=document.getElementById('practical-file-camera');
    const upload=document.getElementById('practical-file-upload');
    const preview=root.querySelector('[data-scan-preview]');
    const previewEmpty=root.querySelector('[data-scan-preview-empty]');
    const progress=root.querySelector('[data-scan-progress]');
    const progressFill=root.querySelector('[data-scan-progress-fill]');
    const progressText=root.querySelector('[data-scan-progress-text]');
    const resultBox=root.querySelector('[data-scan-result]');
    const manualSelect=root.querySelector('[data-scan-student-select]');
    const manualSave=root.querySelector('[data-scan-manual-save]');
    let worker=null;
    let current={ocrText:'',confidence:0,filename:''};
    let previewUrl='';

    function setProgress(label,pct){
      if(!progress) return;
      progress.hidden=false;
      progressText.textContent=label;
      progressFill.style.width=Math.max(2,Math.min(100,pct||0))+'%';
    }

    function stopProgress(){
      if(progress) progress.hidden=true;
    }

    function clearResult(){
      if(!resultBox) return;
      resultBox.hidden=true;
      resultBox.className='practical-scan-result';
      resultBox.replaceChildren();
    }

    function showResult(kind,title,message){
      if(!resultBox) return;
      resultBox.hidden=false;
      resultBox.className='practical-scan-result '+kind;
      resultBox.replaceChildren();
      const strong=document.createElement('strong');strong.textContent=title;
      const p=document.createElement('p');p.textContent=message||'';
      resultBox.append(strong,p);
    }

    function showPreview(file){
      if(previewUrl) URL.revokeObjectURL(previewUrl);
      previewUrl=URL.createObjectURL(file);
      preview.src=previewUrl;preview.hidden=false;
      if(previewEmpty) previewEmpty.hidden=true;
    }

    async function imageToCanvas(file){
      const img=new Image();
      const url=URL.createObjectURL(file);
      try{
        await new Promise((resolve,reject)=>{img.onload=resolve;img.onerror=()=>reject(new Error('The selected image could not be opened.'));img.src=url;});
        const maxSide=1900;
        const scale=Math.min(1,maxSide/Math.max(img.naturalWidth||1,img.naturalHeight||1));
        const canvas=document.createElement('canvas');
        canvas.width=Math.max(1,Math.round(img.naturalWidth*scale));
        canvas.height=Math.max(1,Math.round(img.naturalHeight*scale));
        const ctx=canvas.getContext('2d',{willReadFrequently:false});
        if('filter' in ctx) ctx.filter='grayscale(1) contrast(1.28)';
        ctx.drawImage(img,0,0,canvas.width,canvas.height);
        return canvas;
      } finally {
        URL.revokeObjectURL(url);
      }
    }

    async function pdfFirstPageToCanvas(file){
      if(!window.pdfjsLib) throw new Error('PDF reader could not load. Check the internet connection and refresh this page.');
      window.pdfjsLib.GlobalWorkerOptions.workerSrc='https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';
      const bytes=new Uint8Array(await file.arrayBuffer());
      const pdf=await window.pdfjsLib.getDocument({data:bytes}).promise;
      const page=await pdf.getPage(1);
      const base=page.getViewport({scale:1});
      const maxSide=1900;
      const scale=Math.min(2.2,maxSide/Math.max(base.width,base.height));
      const viewport=page.getViewport({scale:Math.max(1.25,scale)});
      const canvas=document.createElement('canvas');
      canvas.width=Math.max(1,Math.round(viewport.width));canvas.height=Math.max(1,Math.round(viewport.height));
      const ctx=canvas.getContext('2d',{alpha:false});
      await page.render({canvasContext:ctx,viewport:viewport}).promise;
      return canvas;
    }

    function showCanvasPreview(canvas){
      if(previewUrl){URL.revokeObjectURL(previewUrl);previewUrl='';}
      preview.src=canvas.toDataURL('image/jpeg',.86);preview.hidden=false;
      if(previewEmpty) previewEmpty.hidden=true;
    }

    async function getWorker(){
      if(worker) return worker;
      if(!window.Tesseract) throw new Error('OCR engine could not load. Check the internet connection and refresh this page.');
      setProgress('Loading OCR engine…',8);
      worker=await window.Tesseract.createWorker('eng',1,{
        workerPath:'https://cdnjs.cloudflare.com/ajax/libs/tesseract.js/5.1.1/worker.min.js',
        corePath:'https://cdn.jsdelivr.net/npm/tesseract.js-core@5.1.1',
        langPath:'https://tessdata.projectnaptha.com/4.0.0',
        logger:function(m){
          if(!m) return;
          const value=Math.round((m.progress||0)*100);
          if(m.status==='recognizing text') setProgress('Reading name and roll number…',15+Math.round(value*.8));
          else if(m.status) setProgress(String(m.status).replace(/^./,c=>c.toUpperCase())+'…',Math.max(5,Math.min(20,value)));
        }
      });
      return worker;
    }

    async function postScan(extra){
      const payload=Object.assign({ocr_text:current.ocrText,confidence:current.confidence,filename:current.filename},extra||{});
      const response=await fetch(scanUrl,{
        method:'POST',
        credentials:'same-origin',
        headers:{'Content-Type':'application/json','X-CSRF-Token':csrf,'Accept':'application/json'},
        body:JSON.stringify(payload)
      });
      let data={};
      try{data=await response.json();}catch(_e){}
      if(!response.ok||!data.ok) throw new Error(data.error||'The scan could not be saved.');
      return data;
    }

    function removeManualOption(studentId){
      if(!manualSelect) return;
      const option=manualSelect.querySelector('option[value="'+String(studentId)+'"]');
      if(option) option.remove();
      manualSelect.value='';
    }

    function updateCounts(){
      const received=document.getElementById('practical-files-received-count');
      const missing=document.getElementById('practical-files-missing-count');
      if(received) received.textContent=String((parseInt(received.textContent,10)||0)+1);
      if(missing) missing.textContent=String(Math.max(0,(parseInt(missing.textContent,10)||0)-1));
      const header=root.querySelector('.practical-file-received-badge strong');
      if(header) header.textContent=received?received.textContent:String((parseInt(header.textContent,10)||0)+1);
    }

    function markReceived(data){
      if(!data||!data.student) return;
      const row=document.querySelector('[data-practical-student-row="'+String(data.student.id)+'"]');
      const cell=row&&row.querySelector('[data-practical-file-cell]');
      const wasMissing=!!(cell&&cell.querySelector('.practical-file-missing'));
      if(cell){
        cell.replaceChildren();
        const wrap=document.createElement('div');wrap.className='practical-file-cell';
        const badge=document.createElement('span');badge.className='badge practical-file-received';badge.textContent='Received';
        const small=document.createElement('small');small.textContent='Just now';
        wrap.append(badge,small);
        if(data.submission_id&&deleteTemplate){
          const form=document.createElement('form');form.method='post';form.action=deleteTemplate.replace(/\/0\/delete$/,'/'+String(data.submission_id)+'/delete');
          form.addEventListener('submit',function(e){if(!window.confirm('Remove this practical-file receipt?')) e.preventDefault();});
          const token=document.createElement('input');token.type='hidden';token.name='csrf_token';token.value=csrf;
          const btn=document.createElement('button');btn.type='submit';btn.className='practical-file-remove';btn.title='Remove receipt';btn.setAttribute('aria-label','Remove file receipt');btn.textContent='×';
          form.append(token,btn);wrap.append(form);
        }
        cell.append(wrap);
      }
      removeManualOption(data.student.id);
      if(wasMissing&&!data.duplicate) updateCounts();
    }

    function renderConfirmation(data){
      resultBox.hidden=false;
      resultBox.className='practical-scan-result warning';
      resultBox.replaceChildren();
      const title=document.createElement('strong');title.textContent='Please confirm the student';
      const detected=document.createElement('p');
      const parts=[];
      if(data.detected&&data.detected.roll_no) parts.push('Detected roll: '+data.detected.roll_no);
      if(data.detected&&data.detected.name) parts.push('Detected name: '+data.detected.name);
      detected.textContent=parts.length?parts.join(' · '):'OCR was not confident enough for automatic saving.';
      resultBox.append(title,detected);
      const list=document.createElement('div');list.className='practical-scan-candidates';
      (data.candidates||[]).forEach(function(candidate){
        if(!candidate.student_id||candidate.score<20) return;
        const button=document.createElement('button');button.type='button';button.className='btn secondary small';
        button.textContent=candidate.roll_no+' — '+candidate.name+' ('+Math.round(candidate.score)+'%)';
        button.addEventListener('click',()=>confirmStudent(candidate.student_id));
        list.append(button);
      });
      if(list.children.length) resultBox.append(list);
    }

    async function confirmStudent(studentId){
      if(!studentId){showResult('error','Choose a student','Select the correct student before saving.');return;}
      try{
        setProgress('Saving practical-file receipt…',92);
        const data=await postScan({practical_student_id:studentId});
        stopProgress();markReceived(data);
        showResult(data.duplicate?'warning':'success',data.duplicate?'Already received':'File received',data.student.roll_no+' — '+data.student.name+(data.duplicate?' is already marked as received.':' was saved successfully.'));
      }catch(err){stopProgress();showResult('error','Could not save',err.message);}
    }

    async function processFile(file){
      if(!file) return;
      clearResult();
      const isPdf=(file.type==='application/pdf'||/\.pdf$/i.test(file.name||''));
      const isImage=/^image\//i.test(file.type||'');
      if(!isPdf&&!isImage){showResult('error','Unsupported file','Please photograph the first page or upload an image/PDF file.');return;}
      if(file.size>20*1024*1024){showResult('error','File too large','Use an image or PDF smaller than 20 MB.');return;}
      current={ocrText:'',confidence:0,filename:file.name||'camera-photo'};
      if(isImage) showPreview(file);
      try{
        setProgress(isPdf?'Opening PDF first page…':'Preparing first page…',4);
        const canvas=isPdf?await pdfFirstPageToCanvas(file):await imageToCanvas(file);
        if(isPdf) showCanvasPreview(canvas);
        const ocrWorker=await getWorker();
        setProgress('Reading name and roll number…',22);
        const recognition=await ocrWorker.recognize(canvas,{rotateAuto:true});
        current.ocrText=(recognition&&recognition.data&&recognition.data.text)||'';
        current.confidence=Number((recognition&&recognition.data&&recognition.data.confidence)||0);
        setProgress('Matching student in this register…',94);
        const data=await postScan();
        stopProgress();
        if(data.status==='saved'||data.status==='duplicate'){
          markReceived(data);
          const details=data.student.roll_no+' — '+data.student.name;
          showResult(data.duplicate?'warning':'success',data.duplicate?'Already received':'Matched & saved',details+(data.score?' · Match '+Math.round(data.score)+'%':''));
        }else if(data.status==='needs_confirmation') renderConfirmation(data);
      }catch(err){
        stopProgress();
        showResult('error','Scan not completed',err&&err.message?err.message:'The image could not be read.');
      }finally{
        if(camera) camera.value='';
        if(upload) upload.value='';
      }
    }

    [camera,upload].forEach(function(input){if(input) input.addEventListener('change',function(){processFile(input.files&&input.files[0]);});});
    if(manualSave) manualSave.addEventListener('click',function(){confirmStudent(manualSelect&&manualSelect.value);});
    window.addEventListener('beforeunload',function(){if(worker&&worker.terminate) worker.terminate().catch(function(){});},{once:true});
  });
})();
