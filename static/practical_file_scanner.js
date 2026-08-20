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
    const experimentSelect=root.querySelector('[data-scan-experiment-select]');
    const camera=document.getElementById('practical-file-camera');
    const scanButton=root.querySelector('label[for="practical-file-camera"]');
    const progress=root.querySelector('[data-scan-progress]');
    const progressText=root.querySelector('[data-scan-progress-text]');
    const resultBox=root.querySelector('[data-scan-result]');
    const manualSelect=root.querySelector('[data-scan-student-select]');
    const manualSave=root.querySelector('[data-scan-manual-save]');
    const selectedCount=root.querySelector('[data-scan-received-count]');
    const selectedLabel=root.querySelector('[data-scan-received-label]');
    let worker=null;
    let workerPromise=null;
    let current={ocrText:'',confidence:0};

    function selectedExperiment(){
      if(!experimentSelect||!experimentSelect.value) return null;
      const option=experimentSelect.options[experimentSelect.selectedIndex];
      return {id:experimentSelect.value,no:(option&&option.dataset.experimentNo)||'',label:(option&&option.textContent)||''};
    }

    function requireExperiment(){
      const experiment=selectedExperiment();
      if(experiment) return experiment;
      showResult('warning','Select experiment first','Choose the experiment whose practical record you are scanning.');
      if(experimentSelect) experimentSelect.focus();
      return null;
    }

    function setProgress(label){
      if(!progress) return;
      progress.hidden=false;
      if(progressText) progressText.textContent=label;
    }

    function stopProgress(){if(progress) progress.hidden=true;}

    function clearResult(){
      if(!resultBox) return;
      resultBox.hidden=true;
      resultBox.className='practical-scan-result practical-scan-result-compact';
      resultBox.replaceChildren();
    }

    function showResult(kind,title,message){
      if(!resultBox) return;
      resultBox.hidden=false;
      resultBox.className='practical-scan-result practical-scan-result-compact '+kind;
      resultBox.replaceChildren();
      const strong=document.createElement('strong');strong.textContent=title;
      const p=document.createElement('p');p.textContent=message||'';
      resultBox.append(strong,p);
    }

    function ocrStatusLabel(status,progressValue){
      const value=Math.max(0,Math.min(100,Math.round(Number(progressValue||0)*100)));
      const text=String(status||'').toLowerCase();
      if(text.includes('recognizing')) return 'Scanning name and roll number… '+value+'%';
      if(text.includes('language')) return 'Loading handwriting reader…';
      if(text.includes('core')||text.includes('initializing')) return 'Starting scanner…';
      if(text.includes('loading')) return 'Loading scanner…';
      return 'Preparing scanner…';
    }

    function logger(message){
      if(!message) return;
      if(progress&&!progress.hidden) setProgress(ocrStatusLabel(message.status,message.progress));
    }

    function promiseTimeout(promise,ms,message,onLateResolve){
      let timer;
      const timeout=new Promise((_,reject)=>{
        timer=setTimeout(()=>reject(new Error(message)),ms);
      });
      promise.then(function(value){
        if(timer===null&&onLateResolve) onLateResolve(value);
      }).catch(function(){});
      return Promise.race([promise,timeout]).finally(function(){
        if(timer){clearTimeout(timer);timer=null;}
      });
    }

    async function configureWorker(instance){
      if(instance&&instance.setParameters){
        const sparse=(window.Tesseract&&window.Tesseract.PSM&&window.Tesseract.PSM.SPARSE_TEXT)||'11';
        try{
          await instance.setParameters({
            tessedit_pageseg_mode:sparse,
            preserve_interword_spaces:'1',
            user_defined_dpi:'300'
          });
        }catch(_e){}
      }
      return instance;
    }

    async function createWorkerAttempt(options,timeoutMs){
      const creation=window.Tesseract.createWorker('eng',1,Object.assign({logger:logger},options||{}));
      return promiseTimeout(
        creation,
        timeoutMs,
        'The OCR engine took too long to start.',
        function(lateWorker){if(lateWorker&&lateWorker.terminate) lateWorker.terminate().catch(function(){});}
      );
    }

    async function createReliableWorker(){
      if(!window.Tesseract) throw new Error('OCR engine could not load. Check the internet connection and refresh this page.');
      // First use Tesseract.js v5 defaults. They use the smaller jsDelivr v5
      // English model and avoid the older projectnaptha language endpoint.
      try{
        return await configureWorker(await createWorkerAttempt({},30000));
      }catch(firstError){
        // Some institutional networks block jsDelivr. Retry through an
        // alternate CDN combination instead of leaving the UI stuck forever.
        try{
          return await configureWorker(await createWorkerAttempt({
            workerPath:'https://cdnjs.cloudflare.com/ajax/libs/tesseract.js/5.1.1/worker.min.js',
            corePath:'https://unpkg.com/tesseract.js-core@5.1.1',
            langPath:'https://unpkg.com/@tesseract.js-data/eng@1.0.0/4.0.0_best_int'
          },30000));
        }catch(_secondError){
          throw new Error('Scanner could not start. Please check the internet connection, then try Scan Record again. You can still use Manual confirmation.');
        }
      }
    }

    async function getWorker(){
      if(worker) return worker;
      if(workerPromise) return workerPromise;
      workerPromise=createReliableWorker().then(function(instance){
        worker=instance;
        workerPromise=null;
        return instance;
      }).catch(function(error){
        worker=null;
        workerPromise=null;
        throw error;
      });
      return workerPromise;
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
        const ctx=canvas.getContext('2d',{willReadFrequently:true});
        if('filter' in ctx) ctx.filter='grayscale(1) contrast(1.35)';
        ctx.drawImage(img,0,0,canvas.width,canvas.height);
        return canvas;
      } finally {URL.revokeObjectURL(url);}
    }

    function handwritingCanvas(source){
      // High-contrast + slight stroke thickening helps thin handwritten digits
      // without sending the image anywhere outside the browser.
      const scale=Math.min(1.45,2100/Math.max(source.width||1,source.height||1));
      const canvas=document.createElement('canvas');
      canvas.width=Math.max(1,Math.round(source.width*scale));
      canvas.height=Math.max(1,Math.round(source.height*scale));
      const ctx=canvas.getContext('2d',{willReadFrequently:true});
      ctx.drawImage(source,0,0,canvas.width,canvas.height);
      const image=ctx.getImageData(0,0,canvas.width,canvas.height);
      const data=image.data;
      for(let i=0;i<data.length;i+=4){
        const grey=Math.round(data[i]*0.299+data[i+1]*0.587+data[i+2]*0.114);
        const value=grey<205?0:255;
        data[i]=value;data[i+1]=value;data[i+2]=value;data[i+3]=255;
      }
      ctx.putImageData(image,0,0);
      // Thicken the black pen strokes by roughly one CSS pixel. drawImage with
      // multiply is far cheaper than a full morphology pass on large photos.
      ctx.globalCompositeOperation='multiply';
      ctx.globalAlpha=.72;
      ctx.drawImage(canvas,-1,0);ctx.drawImage(canvas,1,0);ctx.drawImage(canvas,0,-1);ctx.drawImage(canvas,0,1);
      ctx.globalAlpha=1;ctx.globalCompositeOperation='source-over';
      return canvas;
    }

    async function recognizeCanvas(ocrWorker,canvas,label){
      setProgress(label||'Scanning name and roll number…');
      const job=ocrWorker.recognize(canvas,{rotateAuto:false});
      return promiseTimeout(job,35000,'The page is taking too long to read. Please retake the photo in good light.');
    }

    async function postScan(extra){
      const experiment=requireExperiment();
      if(!experiment) throw new Error('Select the experiment before saving.');
      const payload=Object.assign({ocr_text:current.ocrText,confidence:current.confidence,experiment_id:experiment.id},extra||{});
      const response=await fetch(scanUrl,{
        method:'POST',credentials:'same-origin',
        headers:{'Content-Type':'application/json','X-CSRF-Token':csrf,'Accept':'application/json'},
        body:JSON.stringify(payload)
      });
      let data={};
      try{data=await response.json();}catch(_e){}
      if(!response.ok||!data.ok) throw new Error(data.error||'The scan could not be saved.');
      return data;
    }

    function recordCell(studentId,experimentId){
      return document.querySelector('[data-record-cell][data-student-id="'+String(studentId)+'"][data-experiment-id="'+String(experimentId)+'"]');
    }

    function isReceived(studentId,experimentId){
      const cell=recordCell(studentId,experimentId);
      return !!(cell&&cell.dataset.received==='1');
    }

    function refreshSelectedExperimentUI(){
      const experiment=selectedExperiment();
      if(!experiment){
        if(selectedCount) selectedCount.textContent='—';
        if(selectedLabel) selectedLabel.textContent='for selected experiment';
      }else{
        const option=experimentSelect.options[experimentSelect.selectedIndex];
        let count=Number(option&&option.dataset.receivedCount||0);
        const cells=document.querySelectorAll('[data-record-cell][data-experiment-id="'+String(experiment.id)+'"][data-received="1"]');
        if(cells.length||count===0) count=cells.length;
        if(selectedCount) selectedCount.textContent=String(count);
        if(selectedLabel) selectedLabel.textContent='for Exp '+experiment.no;
      }
      if(manualSelect){
        Array.from(manualSelect.options).forEach(function(option,index){
          if(index===0) return;
          option.disabled=!!(experiment&&isReceived(option.value,experiment.id));
        });
        if(manualSelect.selectedOptions[0]&&manualSelect.selectedOptions[0].disabled) manualSelect.value='';
      }
      clearResult();
    }

    function updateOverallCounts(delta){
      if(!delta) return;
      const received=document.getElementById('practical-records-received-count');
      const missing=document.getElementById('practical-records-missing-count');
      if(received) received.textContent=String(Math.max(0,(parseInt(received.textContent,10)||0)+delta));
      if(missing) missing.textContent=String(Math.max(0,(parseInt(missing.textContent,10)||0)-delta));
    }

    function incrementStudentSummary(studentId){
      const cell=document.querySelector('[data-record-summary-cell][data-student-id="'+String(studentId)+'"] strong');
      if(cell) cell.textContent=String((parseInt(cell.textContent,10)||0)+1);
    }

    function markReceived(data){
      if(!data||!data.student||!data.experiment) return;
      const cell=recordCell(data.student.id,data.experiment.id);
      const wasMissing=!!(cell&&cell.dataset.received!=='1');
      if(cell){
        cell.dataset.received='1';cell.replaceChildren();
        const wrap=document.createElement('div');wrap.className='practical-file-cell';
        const badge=document.createElement('span');badge.className='badge practical-file-received';badge.textContent='Received';
        const small=document.createElement('small');small.textContent='Just now';wrap.append(badge,small);
        if(data.submission_id&&deleteTemplate){
          const form=document.createElement('form');form.method='post';form.action=deleteTemplate.replace(/\/0\/delete$/,'/'+String(data.submission_id)+'/delete');
          form.addEventListener('submit',function(e){if(!window.confirm('Remove the Experiment '+data.experiment.no+' record receipt?')) e.preventDefault();});
          const token=document.createElement('input');token.type='hidden';token.name='csrf_token';token.value=csrf;
          const exp=document.createElement('input');exp.type='hidden';exp.name='experiment_id';exp.value=String(data.experiment.id);
          const btn=document.createElement('button');btn.type='submit';btn.className='practical-file-remove';btn.title='Remove receipt';btn.setAttribute('aria-label','Remove record receipt');btn.textContent='×';
          form.append(token,exp,btn);wrap.append(form);
        }
        cell.append(wrap);
      }
      if(wasMissing&&!data.duplicate){
        updateOverallCounts(1);incrementStudentSummary(data.student.id);
        if(experimentSelect){
          const option=Array.from(experimentSelect.options).find(o=>o.value===String(data.experiment.id));
          if(option) option.dataset.receivedCount=String(data.experiment_received_count||((parseInt(option.dataset.receivedCount,10)||0)+1));
        }
      }
      refreshSelectedExperimentUI();
    }

    function renderConfirmation(data){
      resultBox.hidden=false;resultBox.className='practical-scan-result practical-scan-result-compact warning';resultBox.replaceChildren();
      const title=document.createElement('strong');title.textContent='Please confirm the student';
      const detected=document.createElement('p');const parts=[];
      if(data.detected&&data.detected.roll_no) parts.push('Detected roll: '+data.detected.roll_no);
      if(data.detected&&data.detected.name) parts.push('Detected name: '+data.detected.name);
      detected.textContent=parts.length?parts.join(' · '):'The handwriting was not clear enough for safe automatic saving.';
      resultBox.append(title,detected);
      const list=document.createElement('div');list.className='practical-scan-candidates';
      (data.candidates||[]).forEach(function(candidate){
        if(!candidate.student_id||candidate.score<20) return;
        if(data.experiment&&isReceived(candidate.student_id,data.experiment.id)) return;
        const button=document.createElement('button');button.type='button';button.className='btn secondary small';
        button.textContent=candidate.roll_no+' — '+candidate.name;
        button.addEventListener('click',()=>confirmStudent(candidate.student_id));list.append(button);
      });
      if(list.children.length) resultBox.append(list);
    }

    async function confirmStudent(studentId){
      const experiment=requireExperiment();
      if(!experiment) return;
      if(!studentId){showResult('error','Choose a student','Select the correct student before saving.');return;}
      if(isReceived(studentId,experiment.id)){showResult('warning','Already received','This student is already marked as received for Experiment '+experiment.no+'.');return;}
      try{
        setProgress('Saving record…');
        const data=await postScan({practical_student_id:studentId});stopProgress();markReceived(data);
        showResult(data.duplicate?'warning':'success',data.duplicate?'Already received':'✓ Record received',data.student.roll_no+' — '+data.student.name);
      }catch(err){stopProgress();showResult('error','Could not save',err.message);}
    }

    async function processFile(file){
      if(!file) return;
      const experiment=requireExperiment();
      if(!experiment){if(camera) camera.value='';return;}
      clearResult();
      const isImage=/^image\//i.test(file.type||'');
      if(!isImage){showResult('error','Unsupported scan','Please scan the first page as an image.');return;}
      if(file.size>20*1024*1024){showResult('error','Scan too large','Use an image smaller than 20 MB.');return;}
      current={ocrText:'',confidence:0};
      try{
        setProgress('Preparing photo…');
        const canvas=await imageToCanvas(file);
        setProgress('Starting scanner…');
        const ocrWorker=await getWorker();

        const first=await recognizeCanvas(ocrWorker,canvas,'Scanning name and roll number…');
        current.ocrText=(first&&first.data&&first.data.text)||'';
        current.confidence=Number((first&&first.data&&first.data.confidence)||0);
        setProgress('Matching student…');
        let data=await postScan();

        // Handwriting is much harder than printed text. If the first pass is
        // uncertain, automatically try a high-contrast/thick-stroke pass before
        // asking faculty to confirm the student manually.
        if(data.status==='needs_confirmation'){
          const enhanced=handwritingCanvas(canvas);
          const second=await recognizeCanvas(ocrWorker,enhanced,'Trying handwriting enhancement…');
          const secondText=(second&&second.data&&second.data.text)||'';
          const secondConfidence=Number((second&&second.data&&second.data.confidence)||0);
          if(secondText.trim()){
            current.ocrText=[current.ocrText,secondText].filter(Boolean).join('\n');
            current.confidence=Math.max(current.confidence,secondConfidence);
            setProgress('Matching student…');
            data=await postScan();
          }
        }

        stopProgress();
        if(data.status==='saved'||data.status==='duplicate'){
          markReceived(data);
          showResult(data.duplicate?'warning':'success',data.duplicate?'Already received':'✓ Record received',data.student.roll_no+' — '+data.student.name);
        }else if(data.status==='needs_confirmation') renderConfirmation(data);
      }catch(err){
        stopProgress();
        showResult('error','Scan not completed',err&&err.message?err.message:'The page could not be read.');
      }finally{
        if(camera) camera.value='';
      }
    }

    if(camera) camera.addEventListener('change',function(){processFile(camera.files&&camera.files[0]);});
    // Start loading the OCR worker as soon as the user taps Scan Record. The
    // camera/file chooser then opens while the engine warms up in parallel.
    if(scanButton) scanButton.addEventListener('pointerdown',function(){if(selectedExperiment()) getWorker().catch(function(){});});
    if(manualSave) manualSave.addEventListener('click',function(){confirmStudent(manualSelect&&manualSelect.value);});
    if(experimentSelect) experimentSelect.addEventListener('change',refreshSelectedExperimentUI);
    refreshSelectedExperimentUI();
    window.addEventListener('beforeunload',function(){
      if(worker&&worker.terminate) worker.terminate().catch(function(){});
      worker=null;workerPromise=null;
    },{once:true});
  });
})();
