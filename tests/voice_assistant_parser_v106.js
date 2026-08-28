const fs=require('fs');
const vm=require('vm');
const code=fs.readFileSync(require('path').join(__dirname,'..','static','voice_assistant.js'),'utf8');
const sandbox={window:{EXAM_VOICE_CONFIG:{enabled:true,testMode:true}}};
vm.createContext(sandbox);vm.runInContext(code,sandbox);
const api=sandbox.window.EXAM_VOICE_TEST_API;
function ok(cond,msg){if(!cond){console.error('FAIL:',msg);process.exit(1);}console.log('PASS:',msg);}
ok(api.candidateScore('Cloud Computing','Create clud computng all exam for 30 minutes')>=0.74,'typo matches Cloud Computing');
ok(api.candidateScore('Mobile Application Development','MAD Unit 2 test bana do')>=0.95,'MAD acronym is understood');
ok(api.extractDuration('make a test for half an hour')===30,'half an hour = 30 minutes');
ok(api.extractDuration('one hour 30 minutes')===90,'mixed hour/minute duration = 90');
ok(api.extractUnitInfo('second unit ka exam').value==='2','ordinal unit phrasing is understood');
ok(api.isCreateVerb('exam bana do')&&api.hasExamNoun('exam bana do'),'Hinglish create intent is understood');
