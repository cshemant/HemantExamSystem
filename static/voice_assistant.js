(function(){
  'use strict';

  const cfg=window.EXAM_VOICE_CONFIG||{};
  if(!cfg.enabled)return;

  const SpeechRecognition=window.SpeechRecognition||window.webkitSpeechRecognition;
  const PENDING_KEY='exam_voice_pending_command_v2';
  const CONTEXT_KEY='exam_voice_context_v2';
  const HIGHLIGHT_CLASS='voice-assistant-highlight';
  const MATCH_HIGH=0.74;
  const MATCH_MEDIUM=0.61;
  let recognition=null;
  let listening=false;
  let lastFinalTranscript='';
  let confirmAction=null;

  const WORD_NUMBERS={
    zero:0,oh:0,one:1,two:2,three:3,four:4,five:5,six:6,seven:7,eight:8,nine:9,ten:10,
    eleven:11,twelve:12,thirteen:13,fourteen:14,fifteen:15,sixteen:16,seventeen:17,eighteen:18,nineteen:19,
    twenty:20,thirty:30,forty:40,fifty:50,sixty:60,seventy:70,eighty:80,ninety:90,hundred:100
  };
  const ORDINAL_NUMBERS={
    first:1,second:2,third:3,fourth:4,fifth:5,sixth:6,seventh:7,eighth:8,ninth:9,tenth:10,
    eleventh:11,twelfth:12,thirteenth:13,fourteenth:14,fifteenth:15,sixteenth:16,seventeenth:17,eighteenth:18,nineteenth:19,twentieth:20
  };
  const HINGLISH_NUMBERS={
    ek:1,do:2,teen:3,char:4,chaar:4,panch:5,paanch:5,che:6,chhe:6,saat:7,aath:8,nau:9,das:10,
    gyarah:11,barah:12,terah:13,chaudah:14,pandrah:15,solah:16,satrah:17,atharah:18,unnis:19,bees:20,
    tees:30,chalis:40,pachas:50,saath:60,sattar:70,assi:80,nabbe:90
  };
  const HINDI_DIGITS={'०':'0','१':'1','२':'2','३':'3','४':'4','५':'5','६':'6','७':'7','८':'8','९':'9'};
  const SUBJECT_STOPWORDS=new Set(['and','of','the','for','in','to','with','a','an','subject','course','paper','exam','test','quiz','unit','semester']);
  const COMMAND_NOISE=new Set([
    'please','pls','kindly','create','make','prepare','build','generate','setup','set','up','add','new','exam','test','quiz','paper','assessment',
    'for','of','the','a','an','in','on','to','from','with','without','unit','units','minute','minutes','min','mins','hour','hours','all','whole','full',
    'bana','banao','banado','banaao','karo','kar','karna','krdo','kr','ka','ki','ke','mein','me','wala','wali','do','please'
  ]);
  const SUBJECT_ALIASES={
    'mobile application development':['mad','mobile app development','mobile application','android development','android app development'],
    'cloud computing':['cc','cloud'],
    'indian knowledge systems':['iks','indian knowledge system','knowledge systems'],
    'data structures':['ds','dsa','data structure'],
    'theory of computation':['toc','automata theory','computation theory'],
    'computer networks':['cn','networking'],
    'database management systems':['dbms','database management','database'],
    'operating systems':['os','operating system'],
    'object oriented programming':['oop','oops','object oriented'],
    'software engineering':['se','software engg']
  };

  const safeText=(value)=>String(value==null?'':value).trim();
  const currentPath=()=>window.location.pathname.replace(/\/$/,'')||'/';
  const routePath=(url)=>{try{return new URL(url,window.location.origin).pathname.replace(/\/$/,'')||'/';}catch(_e){return String(url||'').replace(/\/$/,'');}};
  const isRoute=(key)=>cfg.routes&&cfg.routes[key]&&currentPath()===routePath(cfg.routes[key]);

  function normalize(value){
    return String(value||'')
      .replace(/[०-९]/g,ch=>HINDI_DIGITS[ch]||ch)
      .toLowerCase()
      .replace(/[’']/g,'')
      .replace(/[^a-z0-9\u0900-\u097f:/.-]+/g,' ')
      .replace(/\s+/g,' ')
      .trim();
  }

  function normalizeLoose(value){
    return normalize(value)
      .replace(/\bset\s+up\b/g,'setup')
      .replace(/\bfull\s+screen\b/g,'fullscreen')
      .replace(/\bone\s+question\s+at\s+a\s+time\b/g,'secure sequential')
      .replace(/\s+/g,' ')
      .trim();
  }

  function htmlEscape(value){
    return String(value==null?'':value).replace(/[&<>'"]/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[ch]));
  }

  function tokens(value){return normalizeLoose(value).split(' ').filter(Boolean);}

  function levenshtein(a,b){
    a=String(a||'');b=String(b||'');
    if(a===b)return 0;if(!a.length)return b.length;if(!b.length)return a.length;
    const prev=Array.from({length:b.length+1},(_v,i)=>i);
    const cur=new Array(b.length+1);
    for(let i=1;i<=a.length;i++){
      cur[0]=i;
      for(let j=1;j<=b.length;j++)cur[j]=Math.min(cur[j-1]+1,prev[j]+1,prev[j-1]+(a[i-1]===b[j-1]?0:1));
      for(let j=0;j<=b.length;j++)prev[j]=cur[j];
    }
    return prev[b.length];
  }

  function similarity(a,b){
    a=normalize(a);b=normalize(b);
    if(!a&&!b)return 1;if(!a||!b)return 0;if(a===b)return 1;
    return 1-(levenshtein(a,b)/Math.max(a.length,b.length));
  }

  function fuzzyTokenMatch(token,candidate,threshold=0.76){
    token=normalize(token);candidate=normalize(candidate);
    if(!token||!candidate)return false;
    if(token===candidate)return true;
    if(Math.min(token.length,candidate.length)<=3)return false;
    return similarity(token,candidate)>=threshold;
  }

  function hasApproxToken(text,choices,threshold=0.76){
    const ts=tokens(text);
    return choices.some(choice=>{
      const ct=tokens(choice);
      if(ct.length===1)return ts.some(t=>fuzzyTokenMatch(t,ct[0],threshold));
      const n=normalizeLoose(text);if(n.includes(normalizeLoose(choice)))return true;
      return ct.every(c=>ts.some(t=>fuzzyTokenMatch(t,c,threshold)));
    });
  }

  function acronymOf(label){
    return tokens(label).filter(w=>!SUBJECT_STOPWORDS.has(w)).map(w=>w[0]).join('');
  }

  function singularVariants(word){
    const out=new Set([word]);
    if(word.endsWith('ies')&&word.length>4)out.add(word.slice(0,-3)+'y');
    if(word.endsWith('s')&&word.length>4)out.add(word.slice(0,-1));
    return [...out];
  }

  function commandCoreTokens(command){
    return tokens(command).filter(t=>!COMMAND_NOISE.has(t)&&!/^[0-9]+$/.test(t)&&t.length>1);
  }

  function candidateAliases(label){
    const canonical=normalizeLoose(label);
    const aliases=new Set([canonical]);
    const ac=acronymOf(canonical);if(ac.length>=2)aliases.add(ac);
    const compact=tokens(canonical).filter(w=>!SUBJECT_STOPWORDS.has(w)).join(' ');if(compact)aliases.add(compact);
    (SUBJECT_ALIASES[canonical]||[]).forEach(a=>aliases.add(normalizeLoose(a)));
    return [...aliases];
  }

  function candidateScore(label,command){
    const canonical=normalizeLoose(label);
    const cmd=normalizeLoose(command);
    if(!canonical)return 0;
    if(cmd.includes(canonical))return 1;
    const aliases=candidateAliases(label);
    for(const alias of aliases){
      if(!alias)continue;
      if(alias.length<=3){if(new RegExp(`(?:^|\\s)${alias.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')}(?:$|\\s)`).test(cmd))return .98;}
      else if(cmd.includes(alias))return .97;
    }

    const subjectTokens=tokens(canonical).filter(t=>!SUBJECT_STOPWORDS.has(t));
    const cmdTokens=commandCoreTokens(cmd);
    if(!subjectTokens.length||!cmdTokens.length)return 0;
    let total=0,matched=0;
    subjectTokens.forEach(st=>{
      let best=0;
      cmdTokens.forEach(ct=>{
        let s=0;
        for(const sv of singularVariants(st))for(const cv of singularVariants(ct))s=Math.max(s,similarity(sv,cv));
        best=Math.max(best,s);
      });
      total+=best;if(best>=.72)matched++;
    });
    const avg=total/subjectTokens.length;
    const coverage=matched/subjectTokens.length;
    let score=.55*avg+.45*coverage;

    // A distinctive first word like "cloud" is useful when it is long enough.
    if(subjectTokens.length>=2){
      const firstBest=Math.max(...cmdTokens.map(ct=>similarity(subjectTokens[0],ct)));
      if(firstBest>=.88)score=Math.max(score,.71+.12*(firstBest-.88)/.12);
    }
    return Math.max(0,Math.min(1,score));
  }

  function rankCandidates(candidates,command){
    return candidates.map(c=>({...c,score:candidateScore(c.label,command)})).sort((a,b)=>b.score-a.score);
  }

  function chooseCandidate(candidates,command){
    const ranked=rankCandidates(candidates,command);
    const best=ranked[0]||null,second=ranked[1]||null;
    if(!best)return {match:null,ranked,confidence:0,ambiguous:false};
    const margin=best.score-(second?second.score:0);
    const ambiguous=best.score<MATCH_HIGH && best.score>=MATCH_MEDIUM && second && second.score>=MATCH_MEDIUM && margin<.10;
    const accepted=best.score>=MATCH_HIGH || (best.score>=MATCH_MEDIUM && margin>=.11);
    return {match:accepted?best:null,ranked,confidence:best.score,ambiguous};
  }

  function readContext(){
    try{
      const value=JSON.parse(sessionStorage.getItem(CONTEXT_KEY)||'null');
      if(!value||Date.now()-Number(value.updatedAt||0)>6*60*60*1000)return {};
      return value;
    }catch(_e){return {};}
  }

  function writeContext(patch){
    const next={...readContext(),...patch,updatedAt:Date.now()};
    try{sessionStorage.setItem(CONTEXT_KEY,JSON.stringify(next));}catch(_e){}
    return next;
  }

  function inferPageContext(){
    const node=document.querySelector('[data-voice-exam-context]');
    if(node){
      const subject=safeText(node.dataset.voiceSubject);
      const title=safeText(node.dataset.voiceExamTitle);
      const examId=safeText(node.dataset.voiceExamId);
      const unitWeights=document.querySelector('input[name="unit_weights"]')?.value||'';
      const onlyUnit=(unitWeights.split(',').map(v=>v.split(':')[0].trim()).filter(Boolean));
      writeContext({subject,title,examTitle:title,examId,unit:onlyUnit.length===1?onlyUnit[0]:'',route:currentPath()});
    }
  }

  // Lightweight test hook: production never enables testMode. It lets release
  // validation exercise the parser without needing a browser DOM.
  if(cfg.testMode){
    window.EXAM_VOICE_TEST_API={normalizeLoose,replaceNumberWords,candidateScore,extractDuration,extractUnitInfo,isCreateVerb,hasExamNoun};
    return;
  }

  function buildUI(){
    const root=document.createElement('div');
    root.id='admin-voice-assistant';
    root.innerHTML=`
      <button type="button" class="voice-fab" id="voice-fab" aria-label="Open Admin Assistant" title="Admin Assistant">
        <span class="voice-fab-icon" aria-hidden="true">🎤</span><span class="voice-fab-label">Assistant</span>
      </button>
      <section class="voice-panel" id="voice-panel" hidden aria-label="Admin Assistant">
        <div class="voice-panel-head">
          <div><strong>Admin Assistant</strong><div class="voice-mini">Speak naturally. Exact command wording is not required.</div></div>
          <button type="button" class="voice-close" id="voice-close" aria-label="Close Admin Assistant">×</button>
        </div>
        <div class="voice-panel-body">
          <div class="voice-language-row">
            <label for="voice-language">Recognition</label>
            <select id="voice-language"><option value="en-IN">English / Hinglish</option><option value="hi-IN">Hindi (India)</option></select>
          </div>
          <div class="voice-status" id="voice-status" aria-live="polite">Ready — say it in your own words.</div>
          <div class="voice-transcript" id="voice-transcript" aria-live="polite">Try: “Cloud Computing ka Unit 2 test bana do, half an hour ka.”</div>
          <div class="voice-actions">
            <button type="button" class="btn" id="voice-listen">🎤 Start listening</button>
            <button type="button" class="btn secondary" id="voice-help">What can I say?</button>
          </div>
          <div class="voice-fallback">
            <label for="voice-command-input">Or type a command naturally</label>
            <div class="voice-type-row"><input id="voice-command-input" autocomplete="off" placeholder="e.g. cloud computng unit 2 test, 30 min"><button type="button" class="btn secondary" id="voice-run">Run</button></div>
          </div>
          <div class="voice-help" id="voice-help-box" hidden>
            <strong>No command memorization needed</strong>
            <ul>
              <li>“Make a cloud computing test for half an hour.”</li>
              <li>“Cloud Computing ka Unit 2 exam bana do 30 minute ka.”</li>
              <li>“Give every student 10 questions and turn fullscreen on.”</li>
              <li>“Kal 10 se 11 Section K ke liye Lab 204 me schedule karo.”</li>
              <li>“Open the exam I just created.” / “Activate it.”</li>
              <li>“Show me results.” / “Find student 2026CSE001.”</li>
            </ul>
            <div class="voice-mini"><strong>Smart matching:</strong> minor spelling mistakes, common abbreviations and recent exam context are understood when the meaning is clear.</div>
            <div class="voice-mini"><strong>Protected:</strong> deletion, passwords, role changes, restore/reset and other destructive operations stay manual-only.</div>
          </div>
          <div class="voice-confirm" id="voice-confirm" hidden>
            <strong id="voice-confirm-title">Confirm action</strong>
            <div id="voice-confirm-summary"></div>
            <div class="voice-actions"><button type="button" class="btn" id="voice-confirm-yes">Confirm</button><button type="button" class="btn secondary" id="voice-confirm-no">Cancel</button></div>
          </div>
          <div class="voice-suggestions" id="voice-suggestions" hidden></div>
        </div>
      </section>`;
    document.body.appendChild(root);
    return root;
  }

  const ui=buildUI();
  const fab=ui.querySelector('#voice-fab');
  const panel=ui.querySelector('#voice-panel');
  const closeBtn=ui.querySelector('#voice-close');
  const listenBtn=ui.querySelector('#voice-listen');
  const statusEl=ui.querySelector('#voice-status');
  const transcriptEl=ui.querySelector('#voice-transcript');
  const inputEl=ui.querySelector('#voice-command-input');
  const runBtn=ui.querySelector('#voice-run');
  const languageEl=ui.querySelector('#voice-language');
  const helpBtn=ui.querySelector('#voice-help');
  const helpBox=ui.querySelector('#voice-help-box');
  const confirmBox=ui.querySelector('#voice-confirm');
  const confirmTitle=ui.querySelector('#voice-confirm-title');
  const confirmSummary=ui.querySelector('#voice-confirm-summary');
  const confirmYes=ui.querySelector('#voice-confirm-yes');
  const confirmNo=ui.querySelector('#voice-confirm-no');
  const suggestionsBox=ui.querySelector('#voice-suggestions');

  function openPanel(){panel.hidden=false;fab.setAttribute('aria-expanded','true');}
  function closePanel(){stopListening();panel.hidden=true;fab.setAttribute('aria-expanded','false');}
  function setStatus(message,kind=''){statusEl.textContent=message;statusEl.className='voice-status'+(kind?' '+kind:'');}
  function setTranscript(message){transcriptEl.textContent=message||'';}
  function speak(message){
    if(!('speechSynthesis' in window)||!message)return;
    try{window.speechSynthesis.cancel();const u=new SpeechSynthesisUtterance(message);u.lang=languageEl.value==='hi-IN'?'hi-IN':'en-IN';u.rate=1;window.speechSynthesis.speak(u);}catch(_e){}
  }
  function respond(message,kind=''){openPanel();setStatus(message,kind);speak(message);}

  function clearSuggestions(){suggestionsBox.hidden=true;suggestionsBox.innerHTML='';}

  function showSuggestions(title,items,onChoose){
    confirmBox.hidden=true;helpBox.hidden=true;clearSuggestions();
    suggestionsBox.innerHTML=`<strong>${htmlEscape(title)}</strong><div class="voice-suggestion-list"></div>`;
    const list=suggestionsBox.querySelector('.voice-suggestion-list');
    items.slice(0,4).forEach(item=>{
      const btn=document.createElement('button');btn.type='button';btn.className='voice-suggestion-btn';btn.textContent=item.label;
      btn.addEventListener('click',()=>{clearSuggestions();onChoose(item);});list.appendChild(btn);
    });
    suggestionsBox.hidden=false;openPanel();setStatus('I found more than one possible match. Choose the intended one.','warning');
  }

  function confirm(title,summary,callback,confirmLabel='Confirm'){
    confirmAction=callback;confirmTitle.textContent=title;confirmSummary.innerHTML=summary;confirmYes.textContent=confirmLabel;confirmBox.hidden=false;helpBox.hidden=true;clearSuggestions();openPanel();setStatus('I understood this. Please confirm before I change anything.','warning');confirmYes.focus();
  }

  function cancelConfirm(){confirmAction=null;confirmBox.hidden=true;setStatus('Action cancelled.');}

  function queueForRoute(text,routeKey){
    const target=cfg.routes&&cfg.routes[routeKey];
    if(!target){respond('That page is not available for your account.','error');return true;}
    try{sessionStorage.setItem(PENDING_KEY,JSON.stringify({text,created_at:Date.now()}));}catch(_e){}
    window.location.href=target;return true;
  }

  function navigate(routeKey,label){
    const target=cfg.routes&&cfg.routes[routeKey];
    if(!target){respond(`${label||'That page'} is not available for your account.`,'error');return true;}
    setStatus(`Opening ${label}…`);window.location.href=target;return true;
  }

  function protectedCommand(text){
    const n=normalizeLoose(text);
    if(n.includes('change role'))return true;
    const protectedPatterns=[
      /\b(delete|remove|erase|drop|wipe|restore|backup|reset)\b/,/\bpassword\b/,/\b(change|modify|set)\s+(?:the\s+)?role\b/,
      /\bdisable\s+staff\b/,/\benable\s+staff\b/,/डिलीट/,/हटाओ/,/पासवर्ड/,/रोल बदल/,/रीसेट/
    ];
    return protectedPatterns.some(rx=>rx.test(n));
  }

  function isCreateVerb(text){return hasApproxToken(text,['create','make','prepare','build','setup','generate','add'],.72)||/\b(bana|banao|banado|banaao|taiyar|ready)\b/.test(normalizeLoose(text))||/(बनाओ|बना दो|तैयार)/.test(text);}
  function hasExamNoun(text){return hasApproxToken(text,['exam','test','quiz','paper','assessment'],.73)||/(परीक्षा|टेस्ट)/.test(text);}
  function wantsView(text){return hasApproxToken(text,['open','show','view','see','check','find','search','navigate'],.74)||/\b(khol|kholo|dikhao|dekho|dikhana)\b/.test(normalizeLoose(text))||/(खोलो|दिखाओ|देखो)/.test(text);}

  function navigationIntent(text){
    const n=normalizeLoose(text);
    const routeDefs=[
      ['dashboard','Dashboard',['dashboard','home','main page']],['students','Students',['students','student list','learners']],['groups','Batches & Sections',['batches','batch','sections','groups']],
      ['practicals','Practical Marks',['practical marks','practicals','lab marks']],['theory','Theory Class',['theory class','theory classes']],['attendance','Attendance',['attendance','attendance system','mark attendance','class attendance','hajri']],['question_bank','Question Bank',['question bank','questionbank','bank questions']],
      ['exams','Exams',['exams','exam list','tests']],['results','Results',['results','result','scores','marks']],['analytics','Analytics',['analytics','analysis']],['exam_centre','Exam Centre',['exam centre','exam center']],
      ['security','Security',['security','mfa']],['staff','Staff',['staff','faculty list','teachers']],['system','System',['system tools','system settings']]
    ];
    if(!wantsView(n)&&!/\b(go|take)\s+me\b/.test(n))return false;
    const candidates=[];
    routeDefs.forEach(([key,label,aliases])=>{if(cfg.routes&&cfg.routes[key])aliases.forEach(alias=>candidates.push({key,label,labelForMatch:alias}));});
    let best=null,bestScore=0;
    candidates.forEach(c=>{const score=candidateScore(c.labelForMatch,n);if(score>bestScore){best=c;bestScore=score;}});
    if(best&&bestScore>=.64)return navigate(best.key,best.label);
    return false;
  }

  function numberPhraseValue(phrase){
    const ts=normalize(phrase).split(' ').filter(Boolean);let total=0,current=0,seen=false;
    for(const t of ts){
      if(/^\d+(?:\.\d+)?$/.test(t)){current+=Number(t);seen=true;continue;}
      if(Object.prototype.hasOwnProperty.call(ORDINAL_NUMBERS,t)){current+=ORDINAL_NUMBERS[t];seen=true;continue;}
      if(Object.prototype.hasOwnProperty.call(HINGLISH_NUMBERS,t)){current+=HINGLISH_NUMBERS[t];seen=true;continue;}
      if(!Object.prototype.hasOwnProperty.call(WORD_NUMBERS,t))continue;
      const v=WORD_NUMBERS[t];seen=true;
      if(v===100){current=(current||1)*100;}else current+=v;
    }
    total+=current;return seen?total:null;
  }

  function replaceNumberWords(text){
    let out=String(text||'').replace(/[०-९]/g,ch=>HINDI_DIGITS[ch]||ch);
    const dictionary={...WORD_NUMBERS,...ORDINAL_NUMBERS,...HINGLISH_NUMBERS};
    const keys=Object.keys(dictionary).sort((a,b)=>b.length-a.length).join('|');
    const rx=new RegExp(`\\b(?:${keys})(?:[ -]+(?:and[ -]+)?(?:${keys}))*\\b`,'gi');
    out=out.replace(rx,m=>{const v=numberPhraseValue(m);return v==null?m:String(v);});
    return out;
  }

  function extractUnitInfo(text){
    const n=normalizeLoose(replaceNumberWords(text));
    if(/\b(all units?|whole syllabus|full syllabus|complete syllabus|entire syllabus|all chapters?)\b/.test(n)||/(सभी यूनिट|पूरा सिलेबस)/.test(text))return {specified:true,all:true,value:''};
    let m=n.match(/\bunit\s*(?:number\s*)?(\d{1,2}|[a-z])\b/);
    if(!m)m=n.match(/\b(\d{1,2})(?:st|nd|rd|th)\s+unit\b/);
    if(!m)m=n.match(/\b(\d{1,2})\s*(?:number\s*)?unit\b/);
    if(m)return {specified:true,all:false,value:m[1]};
    return {specified:false,all:true,value:''};
  }

  function extractDuration(text){
    const raw=normalizeLoose(replaceNumberWords(text));
    if(/\bhalf\s+(?:an\s+)?hour\b|\baadha\s+ghanta\b|\badha\s+ghanta\b/.test(raw))return 30;
    if(/\bquarter\s+(?:of\s+an\s+|an\s+)?hour\b/.test(raw))return 15;
    let m=raw.match(/\b(\d+(?:\.\d+)?)\s*(?:hours?|hrs?|ghanta|ghante)\b/);
    let hours=m?Number(m[1]):0;
    let minutes=0;
    const mm=raw.match(/\b(\d{1,3})\s*(?:minutes?|mins?|min|minute|मिनट)\b/);if(mm)minutes=Number(mm[1]);
    if(/\b(?:1|one)\s+(?:and\s+)?(?:a\s+)?half\s+hours?\b/.test(raw))hours=1.5;
    if(hours>0)return Math.max(1,Math.min(600,Math.round(hours*60+minutes)));
    if(minutes>0)return Math.max(1,Math.min(600,minutes));
    m=raw.match(/\bduration\s*(?:is|to|of)?\s*(\d{1,3})\b/);return m?Math.max(1,Math.min(600,Number(m[1]))):null;
  }

  function extractTitle(text,unitInfo,subjectName){
    const raw=replaceNumberWords(text).trim();
    const m=raw.match(/(?:\btitle\b|\bcalled\b|\bnamed\b)\s*(?:is\s*)?["“']?(.+?)["”']?(?=\s+(?:for\s+)?\d+\s*(?:minutes?|mins?|hours?)|$)/i);
    if(m&&m[1])return m[1].trim().replace(/[.]+$/,'');
    if(unitInfo&&!unitInfo.all&&unitInfo.value)return `Unit ${unitInfo.value} - Set A`;
    return subjectName?`${subjectName} - Set A`:'Voice Draft Exam';
  }

  function subjectCandidatesFromSelect(select){
    if(!select)return [];
    return [...select.options].filter(o=>o.value).map(o=>({label:safeText(o.textContent),option:o,value:o.value}));
  }

  function catalogSubjectCandidates(){
    const rows=Array.isArray(window.EXAM_VOICE_SUBJECT_CATALOG)?window.EXAM_VOICE_SUBJECT_CATALOG:[];
    return rows.map(r=>({label:safeText(r.name),catalog:r,value:String(r.id||'')})).filter(r=>r.label);
  }

  function resolveSubject(select,text,onResolved){
    const available=subjectCandidatesFromSelect(select);
    const result=chooseCandidate(available,text);
    if(result.match){onResolved(result.match,result.confidence);return true;}
    if(result.ambiguous){
      showSuggestions('Which subject did you mean?',result.ranked.filter(r=>r.score>=MATCH_MEDIUM).slice(0,4),chosen=>onResolved(chosen,chosen.score));return true;
    }

    const allResult=chooseCandidate(catalogSubjectCandidates(),text);
    if(allResult.match){
      const row=allResult.match.catalog||{};
      if(Number(row.approved_count||0)<=0){respond(`I matched “${allResult.match.label}”, but it has no approved Question Bank questions available for exam creation yet. Approve or add questions first.`,'warning');return true;}
      respond(`I matched “${allResult.match.label}”, but it is not currently available in the Create Exam subject list. Refresh the Exams page and check the Question Bank approval status.`,'warning');return true;
    }

    const top=(result.ranked.length?result.ranked:rankCandidates(available,text)).filter(r=>r.score>.35).slice(0,3);
    if(top.length){showSuggestions('I could not confidently identify the subject. Did you mean:',top,chosen=>onResolved(chosen,chosen.score));return true;}
    respond('I could not identify the subject. You can say it approximately—for example “cloud computng”, “MAD”, or the subject name.','error');return true;
  }

  function createExamCommand(text){
    const n=normalizeLoose(replaceNumberWords(text));
    const explicitCreate=isCreateVerb(n)&&hasExamNoun(n);
    const naturalNeed=/\b(want|need|conduct|hold)\b/.test(n)&&hasExamNoun(n)&&!wantsView(n);
    const shorthandCreate=hasExamNoun(n)&&!wantsView(n)&&Boolean(extractDuration(n)||/\bunit\b/.test(n))&&!/\b(activate|deactivate|approve|approval|schedule|session)\b/.test(n);
    if(!explicitCreate&&!naturalNeed&&!shorthandCreate)return false;
    if(!isRoute('exams'))return queueForRoute(text,'exams');

    const subjectSelect=document.getElementById('existing-subject-exam-subject');
    const unitSelect=document.getElementById('existing-subject-exam-unit');
    if(!subjectSelect){respond('The existing-subject exam form is not available on this page.','error');return true;}

    const finish=(subjectMatch,confidence)=>{
      const subjectOption=subjectMatch.option;
      if(!subjectOption)return;
      subjectSelect.value=subjectOption.value;subjectSelect.dispatchEvent(new Event('change',{bubbles:true}));
      const unitInfo=extractUnitInfo(n);
      if(unitInfo.specified&&!unitInfo.all&&unitSelect){
        const rankedUnits=[...unitSelect.options].filter(o=>o.value).map(o=>({label:safeText(o.textContent),option:o,value:o.value}));
        const exact=rankedUnits.find(c=>normalize(c.value)===normalize(unitInfo.value)||normalize(c.label)===`unit ${normalize(unitInfo.value)}`||normalize(c.label)===normalize(unitInfo.value));
        if(exact)unitSelect.value=exact.option.value;
        else{respond(`I understood Unit ${unitInfo.value}, but that unit is not available for ${subjectOption.textContent.trim()}.`,'error');return;}
      }else if(unitSelect)unitSelect.value='';

      const duration=extractDuration(n)||20;
      const form=subjectSelect.closest('form');
      const titleInput=form&&form.querySelector('[name="exam_title"]');
      const durationInput=form&&form.querySelector('[name="duration"]');
      const subjectName=subjectOption.textContent.trim();
      const title=extractTitle(text,unitInfo,subjectName);
      if(titleInput)titleInput.value=title;if(durationInput)durationInput.value=String(duration);
      const unitLabel=unitInfo.specified&&!unitInfo.all?`Unit ${unitInfo.value}`:'All Units';
      const correction=confidence<.97?'<div class="voice-smart-note">✓ Subject name was matched using typo/alias tolerance.</div>':'';
      const summary=`${correction}<div class="voice-summary-grid"><span>Action</span><strong>Create draft exam</strong><span>Subject</span><strong>${htmlEscape(subjectName)}</strong><span>Unit</span><strong>${htmlEscape(unitLabel)}</strong><span>Title</span><strong>${htmlEscape(title)}</strong><span>Duration</span><strong>${duration} minutes</strong></div>`;
      confirm('Create this exam?',summary,()=>{writeContext({subject:subjectName,unit:unitInfo.all?'':unitInfo.value,examTitle:title,title,route:'exams'});if(form){setStatus('Creating draft exam…');form.requestSubmit();}},'Confirm & Create');
    };

    resolveSubject(subjectSelect,n,finish);return true;
  }

  function getBlueprintForm(){const input=document.querySelector('input[name="question_count"]');return input?input.closest('form'):null;}
  function checkboxChange(form,name,value,label,changes){const el=form&&form.querySelector(`[name="${name}"]`);if(!el)return false;el.checked=value;changes.push(`${label}: ${value?'On':'Off'}`);return true;}

  function blueprintCommand(text){
    const n=normalizeLoose(replaceNumberWords(text));
    const phrases=['questions per student','question per student','each student','every student','pool size','question pool','easy','medium','hard','fullscreen','shuffle','randomize','randomise','secure sequential','question at a time','exam pin','rotating pin','strict start','auto submit','hide results','defer results','ip roll','candidate check','heartbeat','grace period','minimum time','min time','generate pool','refresh pool'];
    if(!phrases.some(p=>n.includes(p))&&!/(student|विद्यार्थी).*(question|प्रश्न)/.test(n))return false;
    const form=getBlueprintForm();if(!form){respond('This sounds like an exam setting. Open that exam’s Blueprint & Sessions page first, or say “open the exam I just created”.','warning');return true;}

    if(/\b(generate|refresh|rebuild|make)\b.*\bpool\b/.test(n)){
      const generate=[...form.querySelectorAll('button')].find(b=>b.value==='generate'||/generate\s*\/\s*refresh pool/i.test(b.textContent));
      if(!generate||generate.disabled){respond('The question pool cannot be generated right now. It may be locked after attempts have started.','error');return true;}
      confirm('Generate question pool?','<p>This will rebuild the exam question pool using the currently saved blueprint settings.</p>',()=>{setStatus('Generating question pool…');form.requestSubmit(generate);},'Confirm & Generate');return true;
    }

    const changes=[];let m;
    const qPatterns=[
      /\b(\d{1,3})\s*questions?\s*(?:per|for)\s*(?:each|every)?\s*student\b/,
      /\b(?:give|set|keep|use)\s*(?:each|every)?\s*student\s*(?:to|with)?\s*(\d{1,3})\s*questions?\b/,
      /\b(?:each|every)\s*student\s*(?:gets?|should get|ko)?\s*(\d{1,3})\s*questions?\b/,
      /\bquestions?\s*per\s*student\s*(?:to|is|as)?\s*(\d{1,3})\b/,
      /\bstudent\s*(?:ko)?\s*(\d{1,3})\s*questions?\b/
    ];
    for(const rx of qPatterns){m=n.match(rx);if(m)break;}
    if(m){const el=form.querySelector('[name="question_count"]');if(el){const v=Math.max(1,Number(m[1]));el.value=String(v);const pool=form.querySelector('[name="pool_size"]');if(pool&&Number(pool.value)<v)pool.value=String(v);changes.push(`Questions per student: ${v}`);}}

    m=n.match(/\bpool\s*(?:size)?\s*(?:to|is|of|with)?\s*(\d{1,4})\b/)||n.match(/\b(?:use|keep|take)\s*(\d{1,4})\s*questions?\s*(?:in|for)\s*(?:the\s*)?pool\b/)||n.match(/\b(\d{1,4})\s*questions?\s*(?:in|for)\s*(?:the\s*)?pool\b/);
    if(m){const el=form.querySelector('[name="pool_size"]');if(el){const v=Math.max(1,Number(m[1]));el.value=String(v);changes.push(`Pool size: ${v}`);}}

    const difficulty={easy:'easy_pct',medium:'medium_pct',hard:'hard_pct'};
    Object.entries(difficulty).forEach(([label,name])=>{
      const dm=n.match(new RegExp(`\\b${label}\\s*(?:to|is|as)?\\s*(\\d{1,3})\\s*(?:percent|%)?`))||n.match(new RegExp(`\\b(\\d{1,3})\\s*(?:percent|%)?\\s*${label}\\b`));
      if(dm){const el=form.querySelector(`[name="${name}"]`);if(el){el.value=String(Math.min(100,Math.max(0,Number(dm[1]))));changes.push(`${label[0].toUpperCase()+label.slice(1)}: ${el.value}%`);}}
    });

    const off=/(?:\bdisable\b|\bturn\s+off\b|\bswitch\s+off\b|\bdont\b|\bdo\s+not\b|\bwithout\b|\bno\s+|\bband\b|\bbandh\b|बंद)/.test(n);
    const on=/(?:\benable\b|\bturn\s+on\b|\bswitch\s+on\b|\buse\b|\bwith\b|\bchalu\b|\bon\b|चालू)/.test(n);
    const desired=off?false:(on?true:null);
    const toggleRules=[
      ['randomize_questions',['randomize','randomise','random questions'],'Randomize questions'],['shuffle_options',['shuffle options','shuffle answers','shuffle choices'],'Shuffle options'],
      ['secure_sequential',['secure sequential','one question at a time','question at a time'],'Secure Sequential'],['require_fullscreen',['fullscreen'],'Full-screen monitoring'],
      ['require_exam_pin',['exam pin','rotating pin'],'Rotating Exam PIN'],['strict_start_window',['strict start','common start'],'Strict start window'],
      ['auto_submit_on_integrity_limit',['auto submit','automatic submit'],'Integrity auto-submit'],['defer_results_until_end',['hide results','defer results','delay results'],'Hide results until end'],
      ['block_ip_roll_switch',['ip roll','same ip','ip lock'],'IP/roll lock'],['require_candidate_checkin',['candidate check','check in','check-in'],'Candidate check-in']
    ];
    toggleRules.forEach(([name,ps,label])=>{
      if(ps.some(p=>n.includes(p))){
        let value=desired;
        if(value===null){
          // Natural imperative such as "shuffle options" or "fullscreen please" means enable.
          value=!/(?:dont|do not|without|no |off|disable|band|bandh|बंद)/.test(n);
        }
        checkboxChange(form,name,value,label,changes);
      }
    });

    const numberRules=[
      ['sequential_min_seconds',/(?:minimum|min)\s*time\s*per\s*question\s*(?:to|is|as)?\s*(\d{1,3})/,'Minimum seconds/question'],
      ['tab_switch_limit',/(?:integrity|violation|tab switch)\s*(?:violation\s*)?limit\s*(?:to|is|as)?\s*(\d{1,2})/,'Integrity violation limit'],
      ['start_grace_minutes',/(?:start\s*)?grace\s*(?:period)?\s*(?:to|is|as)?\s*(\d{1,2})/,'Start grace minutes'],
      ['heartbeat_seconds',/heartbeat\s*(?:interval\s*)?(?:to|is|as)?\s*(\d{1,3})/,'Heartbeat seconds']
    ];
    numberRules.forEach(([name,rx,label])=>{const nm=n.match(rx);if(nm){const el=form.querySelector(`[name="${name}"]`);if(el){el.value=String(Number(nm[1]));changes.push(`${label}: ${Number(nm[1])}`);}}});

    if(!changes.length){respond('I understood that you want to change exam settings, but I need the value. For example: “give each student 10 questions” or “turn fullscreen on”.','warning');return true;}
    const summary='<ul>'+changes.map(c=>`<li>${htmlEscape(c)}</li>`).join('')+'</ul>';
    confirm('Save these exam settings?',summary,()=>{setStatus('Saving blueprint settings…');form.requestSubmit();},'Confirm & Save');return true;
  }

  function parseClock(hourText,minuteText,ampm){let hour=Number(hourText),minute=Number(minuteText||0);const meridian=String(ampm||'').toLowerCase();if(meridian==='pm'&&hour<12)hour+=12;if(meridian==='am'&&hour===12)hour=0;if(hour<0||hour>23||minute<0||minute>59)return null;return {hour,minute};}
  function localDateFromCommand(n){
    const d=new Date();d.setSeconds(0,0);if(/\btomorrow\b|\bkal\b|कल/.test(n))d.setDate(d.getDate()+1);
    let m=n.match(/\b(\d{4})-(\d{1,2})-(\d{1,2})\b/);if(m){d.setFullYear(Number(m[1]),Number(m[2])-1,Number(m[3]));return d;}
    m=n.match(/\b(\d{1,2})[\/.](\d{1,2})[\/.](\d{4})\b/);if(m){d.setFullYear(Number(m[3]),Number(m[2])-1,Number(m[1]));return d;}
    const weekdays=['sunday','monday','tuesday','wednesday','thursday','friday','saturday'];
    const wd=weekdays.findIndex(day=>n.includes(day));if(wd>=0){let delta=(wd-d.getDay()+7)%7;if(delta===0&&/\bnext\b/.test(n))delta=7;d.setDate(d.getDate()+delta);}
    return d;
  }
  function toDatetimeLocal(date,hour,minute){const d=new Date(date);d.setHours(hour,minute,0,0);const pad=v=>String(v).padStart(2,'0');return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;}

  function optionCandidates(select){return select?[...select.options].filter(o=>o.value).map(o=>({label:safeText(o.textContent),option:o,value:o.value})):[];}

  function scheduleCommand(text){
    const n=normalizeLoose(replaceNumberWords(text));
    if(!(/\b(schedule|session|time slot|timeslot|slot)\b/.test(n)||/\b(today|tomorrow|kal|आज|कल)\b/.test(n)&&/\b(?:to|till|until|se)\b/.test(n)))return false;
    const startInput=document.querySelector('input[name="scheduled_start"]');const form=startInput?startInput.closest('form'):null;if(!form){respond('This sounds like scheduling. Open the exam’s Blueprint & Sessions page first.','warning');return true;}
    const groupSelect=form.querySelector('select[name="group_id"]');const endInput=form.querySelector('input[name="scheduled_end"]');const venueInput=form.querySelector('input[name="venue"]');
    const timeMatch=n.match(/(?:\bfrom\s*)?(\d{1,2})(?::(\d{1,2}))?\s*(am|pm)?\s*(?:to|till|until|-|se)\s*(\d{1,2})(?::(\d{1,2}))?\s*(am|pm)?/);
    if(!timeMatch){respond('I understood the scheduling request, but not the time range. You can say “tomorrow 10 to 11” or “kal 10 se 11”.','warning');return true;}
    const start=parseClock(timeMatch[1],timeMatch[2],timeMatch[3]);const end=parseClock(timeMatch[4],timeMatch[5],timeMatch[6]||timeMatch[3]);if(!start||!end){respond('I could not understand that time range.','error');return true;}
    const date=localDateFromCommand(n);const startValue=toDatetimeLocal(date,start.hour,start.minute);let endDate=new Date(date);let endValue=toDatetimeLocal(endDate,end.hour,end.minute);if(new Date(endValue)<=new Date(startValue)){endDate.setDate(endDate.getDate()+1);endValue=toDatetimeLocal(endDate,end.hour,end.minute);}

    const groups=optionCandidates(groupSelect);let groupChoice=null;
    const sectionMatch=n.match(/\bsection\s*([a-z0-9-]+)/)||n.match(/\bsec\s*([a-z0-9-]+)/);
    if(sectionMatch){const needle=normalize(sectionMatch[1]);groupChoice=groups.find(c=>{const label=normalize(c.label);return label.includes(`section ${needle}`)||label.endsWith(` ${needle}`)||label.includes(`- ${needle}`);})||null;}
    if(!groupChoice){const gr=chooseCandidate(groups,n);groupChoice=gr.match;}
    if(!groupChoice){respond('I could not confidently match the batch or section. Say something like “Section K” or the batch name.','error');return true;}

    const venueMatch=n.match(/\b(?:in|at|me|mein)\s+((?:lab|room|hall)\s*[a-z0-9-]+)/)||n.match(/\b((?:lab|room|hall)\s*[a-z0-9-]+)\b/);const venue=venueMatch?venueMatch[1].replace(/\b\w/g,c=>c.toUpperCase()):'';
    groupSelect.value=groupChoice.option.value;startInput.value=startValue;if(endInput)endInput.value=endValue;if(venueInput&&venue)venueInput.value=venue;
    const summary=`<div class="voice-summary-grid"><span>Batch / Section</span><strong>${htmlEscape(groupChoice.label)}</strong><span>Start</span><strong>${htmlEscape(startValue.replace('T',' '))}</strong><span>End</span><strong>${htmlEscape(endValue.replace('T',' '))}</strong><span>Venue</span><strong>${htmlEscape(venue||(venueInput&&venueInput.value)||'Not specified')}</strong></div>`;
    confirm('Save this exam session?',summary,()=>{setStatus('Saving exam session…');form.requestSubmit();},'Confirm Session');return true;
  }

  function examCandidates(){
    return [...document.querySelectorAll('tr[id^="exam-"]')].map(row=>{
      const title=safeText(row.dataset.voiceExamTitle)||safeText(row.querySelector('td strong')?.textContent);const section=row.closest('.admin-exam-subject-group');const subject=safeText(row.dataset.voiceSubject)||safeText(section?.querySelector('h3')?.textContent);return {row,title,subject,label:`${subject} ${title}`.trim()};
    }).filter(x=>x.title);
  }

  function bestExam(text){
    const ctx=readContext();let command=normalizeLoose(text);
    if(/\b(it|this|that|same|last|recent|previous)\b/.test(command)||/\bjust\s+(?:created|made)\b/.test(command))command+=` ${ctx.subject||''} ${ctx.examTitle||ctx.title||''}`;
    command=command.replace(/\b(activate|deactivate|approve|request approval|open|blueprint|configure|exam|test|please|it|this|that|same|last|recent|previous)\b/g,' ').replace(/\s+/g,' ').trim();
    const candidates=examCandidates();if(!candidates.length)return null;
    const ranked=candidates.map(c=>({...c,score:Math.max(candidateScore(c.title,command),candidateScore(c.label,command),.7*candidateScore(c.subject,command))})).sort((a,b)=>b.score-a.score);
    const best=ranked[0],second=ranked[1];if(!best)return null;
    if(best.score>=.72||(best.score>=.60&&best.score-(second?second.score:0)>=.10))return best;
    return null;
  }

  function examStateCommand(text){
    const n=normalizeLoose(text);
    const wantsDeactivate=/\b(deactivate|unpublish|turn off|make inactive|stop exam)\b/.test(n)||/\bbandh\b.*\bexam\b/.test(n);
    const wantsActivate=!wantsDeactivate&&(/\b(activate|publish|turn on|make active|start for students)\b/.test(n)||/\bchalu\b.*\bexam\b/.test(n));
    const wantsRequest=/\b(request|send|ask for)\s+approval\b/.test(n);const wantsApprove=!wantsRequest&&/\bapprove\b/.test(n);
    if(!wantsDeactivate&&!wantsActivate&&!wantsRequest&&!wantsApprove)return false;
    if(!isRoute('exams'))return queueForRoute(text,'exams');
    const candidate=bestExam(n);if(!candidate){respond('I understood the action, but not which exam you mean. Say the subject/title, or first open the exam so I can use that context.','error');return true;}
    const forms=[...candidate.row.querySelectorAll('form')];let form=null,button=null,actionLabel='';
    if(wantsRequest){form=forms.find(f=>/\/approval\/request$/.test(routePath(f.action)));actionLabel='Request Approval';}
    else if(wantsApprove){form=forms.find(f=>/\/approval\/approve$/.test(routePath(f.action)));actionLabel='Approve';}
    else{form=forms.find(f=>/\/toggle$/.test(routePath(f.action)));button=form&&form.querySelector('button');const bt=normalize(button&&button.textContent);if(wantsActivate&&bt.includes('deactivate')){respond(`${candidate.title} is already active.`);candidate.row.scrollIntoView({behavior:'smooth',block:'center'});return true;}if(wantsDeactivate&&!bt.includes('deactivate')){respond(`${candidate.title} is already inactive.`);candidate.row.scrollIntoView({behavior:'smooth',block:'center'});return true;}actionLabel=wantsDeactivate?'Deactivate':'Activate';}
    if(!form){respond(`Your account cannot ${actionLabel.toLowerCase()} this exam from its current state. Check its approval/status controls.`,'error');return true;}
    candidate.row.scrollIntoView({behavior:'smooth',block:'center'});candidate.row.classList.add(HIGHLIGHT_CLASS);setTimeout(()=>candidate.row.classList.remove(HIGHLIGHT_CLASS),4500);writeContext({subject:candidate.subject,examTitle:candidate.title,title:candidate.title});
    const summary=`<div class="voice-summary-grid"><span>Action</span><strong>${htmlEscape(actionLabel)}</strong><span>Subject</span><strong>${htmlEscape(candidate.subject||'General')}</strong><span>Exam</span><strong>${htmlEscape(candidate.title)}</strong></div>`;
    confirm(`${actionLabel} this exam?`,summary,()=>{setStatus(`${actionLabel} request submitted…`);form.requestSubmit(button||undefined);},`Confirm ${actionLabel}`);return true;
  }

  function openBlueprintCommand(text){
    const n=normalizeLoose(text);
    const explicit=/\b(blueprint|settings|sessions?|configure)\b/.test(n);
    const contextual=/\b(open|show|view|go to)\b/.test(n)&&/\b(it|this|that|last|recent|created|exam|test)\b/.test(n);
    if(!explicit&&!contextual)return false;
    if(!isRoute('exams'))return queueForRoute(text,'exams');
    const candidate=bestExam(n);if(!candidate){respond('I could not identify which exam to open. Mention part of the title/subject, or say “open the exam I just created”.','error');return true;}
    const link=[...candidate.row.querySelectorAll('a')].find(a=>/blueprint/i.test(a.textContent));if(!link){respond('Blueprint is not available for that exam.','error');return true;}
    writeContext({subject:candidate.subject,examTitle:candidate.title,title:candidate.title});setStatus(`Opening ${candidate.title}…`);window.location.href=link.href;return true;
  }

  function studentFindCommand(text){
    const n=normalizeLoose(text);if(!(hasApproxToken(n,['student'],.82)&&(wantsView(n)||/\b(find|locate|search)\b/.test(n))))return false;
    if(!isRoute('students'))return queueForRoute(text,'students');
    const query=n.replace(/^.*?\bstudent\b/,'').replace(/\b(please|show|find|search|locate|me)\b/g,' ').replace(/\s+/g,' ').trim();if(!query){respond('Tell me the student roll number or name.','warning');return true;}
    const rows=[...document.querySelectorAll('table tr')].filter(r=>r.querySelector('td'));let matches=rows.filter(r=>normalize(r.textContent).includes(query));
    if(!matches.length){matches=rows.map(r=>({r,score:candidateScore(r.textContent,query)})).filter(x=>x.score>=.72).sort((a,b)=>b.score-a.score).slice(0,5).map(x=>x.r);}
    if(!matches.length){respond(`No visible student record closely matches “${query}”.`,'error');return true;}
    rows.forEach(r=>r.classList.remove(HIGHLIGHT_CLASS));matches.forEach(r=>r.classList.add(HIGHLIGHT_CLASS));matches[0].scrollIntoView({behavior:'smooth',block:'center'});respond(`${matches.length} matching student record${matches.length===1?'':'s'} found.`);return true;
  }

  function activeExamCommand(text){const n=normalizeLoose(text);if(!(wantsView(n)&&/\bactive\s+exams?\b/.test(n)))return false;if(!isRoute('exams'))return queueForRoute(text,'exams');const rows=examCandidates().filter(c=>[...c.row.querySelectorAll('.badge')].some(b=>normalize(b.textContent)==='active'));if(!rows.length){respond('There are no active exams in the list.');return true;}rows.forEach(c=>{c.row.classList.add(HIGHLIGHT_CLASS);setTimeout(()=>c.row.classList.remove(HIGHLIGHT_CLASS),5000);});rows[0].row.scrollIntoView({behavior:'smooth',block:'center'});respond(`${rows.length} active exam${rows.length===1?'':'s'} highlighted.`);return true;}

  function handleCommand(rawText,fromPending=false){
    const text=safeText(rawText);if(!text)return;const normalized=normalizeLoose(replaceNumberWords(text));if(!fromPending){setTranscript(text);inputEl.value=text;}confirmBox.hidden=true;confirmAction=null;clearSuggestions();setStatus('Understanding what you mean…');
    if(protectedCommand(normalized)){respond('For safety, voice cannot execute deletion, password, role, reset, restore, or backup operations. Use the normal admin screen for those actions.','error');return;}
    if(createExamCommand(text))return;if(openBlueprintCommand(text))return;if(examStateCommand(text))return;if(activeExamCommand(text))return;if(studentFindCommand(text))return;if(scheduleCommand(text))return;if(blueprintCommand(text))return;if(navigationIntent(text))return;
    if(/\b(help|commands?|examples?)\b|what can you do|kya kar sakte/.test(normalized)){openPanel();helpBox.hidden=false;setStatus('You can speak naturally; these are examples, not fixed commands.');return;}
    respond('I understood the words, but I am not confident enough to change anything. Try rephrasing naturally or include the subject/exam you mean.','warning');
  }

  function microphoneErrorMessage(code){
    if(code==='not-allowed'||code==='service-not-allowed'){
      if(!window.isSecureContext&&!/^(localhost|127\.0\.0\.1)$/i.test(location.hostname))return 'Microphone access was blocked. On some browsers LAN HTTP addresses have restrictions; allow microphone permission or use the typed assistant. HTTPS is the most reliable option.';
      return 'Microphone access is blocked. Allow microphone permission for this site in the browser, then try again. You can still type naturally below.';
    }
    if(code==='no-speech')return 'I did not hear speech. Try again, or type the request below.';
    if(code==='audio-capture')return 'The browser could not access the microphone. Check the phone/browser microphone permission.';
    if(code==='network')return 'Speech recognition could not reach its recognition service. Typed commands still work.';
    return `Speech recognition error: ${code}. You can still type the request below.`;
  }

  function startListening(){
    openPanel();if(!SpeechRecognition){setStatus('Voice recognition is not supported in this browser. The typed natural-language assistant still works.','error');return;}if(listening){stopListening();return;}
    recognition=new SpeechRecognition();recognition.lang=languageEl.value||'en-IN';recognition.continuous=false;recognition.interimResults=true;recognition.maxAlternatives=3;lastFinalTranscript='';
    recognition.onstart=()=>{listening=true;listenBtn.textContent='■ Stop listening';listenBtn.classList.add('listening');setStatus('Listening — speak normally…','listening');setTranscript('Speak now…');};
    recognition.onresult=(event)=>{let interim='',finalText='';for(let i=event.resultIndex;i<event.results.length;i++){const part=event.results[i][0].transcript||'';if(event.results[i].isFinal)finalText+=part;else interim+=part;}if(finalText){lastFinalTranscript=(lastFinalTranscript+' '+finalText).trim();setTranscript(lastFinalTranscript);}else if(interim)setTranscript(interim);};
    recognition.onerror=(event)=>{const code=event&&event.error?event.error:'recognition error';setStatus(microphoneErrorMessage(code),'error');};
    recognition.onend=()=>{listening=false;listenBtn.textContent='🎤 Start listening';listenBtn.classList.remove('listening');const finalText=lastFinalTranscript.trim();if(finalText){setStatus('I heard you. Interpreting the request…');handleCommand(finalText);}else if(statusEl.classList.contains('listening'))setStatus('No speech detected. Try again.','warning');};
    try{recognition.start();}catch(_e){setStatus('Could not start speech recognition. You can type the same request below.','error');}
  }

  function stopListening(){if(recognition&&listening){try{recognition.stop();}catch(_e){}}listening=false;listenBtn.textContent='🎤 Start listening';listenBtn.classList.remove('listening');}

  fab.addEventListener('click',()=>panel.hidden?openPanel():closePanel());closeBtn.addEventListener('click',closePanel);listenBtn.addEventListener('click',startListening);runBtn.addEventListener('click',()=>handleCommand(inputEl.value));inputEl.addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();handleCommand(inputEl.value);}});helpBtn.addEventListener('click',()=>{helpBox.hidden=!helpBox.hidden;confirmBox.hidden=true;clearSuggestions();});confirmNo.addEventListener('click',cancelConfirm);confirmYes.addEventListener('click',()=>{const action=confirmAction;confirmAction=null;confirmBox.hidden=true;if(typeof action==='function')action();});document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!panel.hidden){if(!confirmBox.hidden)cancelConfirm();else if(!suggestionsBox.hidden)clearSuggestions();else closePanel();}});

  inferPageContext();
  if(!SpeechRecognition){listenBtn.disabled=true;listenBtn.title='Voice recognition is not supported by this browser';setStatus('Typed natural-language commands are ready. Voice recognition is unavailable in this browser.','warning');}
  try{const pending=JSON.parse(sessionStorage.getItem(PENDING_KEY)||'null');if(pending){sessionStorage.removeItem(PENDING_KEY);if(Date.now()-Number(pending.created_at||0)<45000){setTimeout(()=>{openPanel();setTranscript(pending.text||'');handleCommand(pending.text||'',true);},260);}}}catch(_e){try{sessionStorage.removeItem(PENDING_KEY);}catch(_ignore){}}
})();
