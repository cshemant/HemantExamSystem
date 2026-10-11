(function(){
  const root=document.getElementById('android-lab');if(!root)return;
  const $=id=>document.getElementById(id),editor=$('android-source'),status=$('android-status'),output=$('android-output'),build=$('android-build'),download=$('android-download'),help=$('android-install-help'),title=$('android-current-file'),tree=$('android-file-tree'),counts=$('android-file-counts'),qr=$('android-qr'),qrImage=$('android-qr-image'),qrExpiry=$('android-qr-expiry');
  let PACKAGE='com.learnwithhemant.studentapp';
  const manifest=`<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="${PACKAGE}">
    <application android:allowBackup="true" android:label="@string/app_name" android:theme="@style/Theme.StudentApp">
        <activity android:name=".MainActivity" android:exported="true">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>
    </application>
</manifest>`;
  const mainActivity=`package ${PACKAGE};

import android.os.Bundle;
import androidx.activity.EdgeToEdge;
import androidx.appcompat.app.AppCompatActivity;
import androidx.core.graphics.Insets;
import androidx.core.view.ViewCompat;
import androidx.core.view.WindowInsetsCompat;

public class MainActivity extends AppCompatActivity {
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        EdgeToEdge.enable(this);
        setContentView(R.layout.activity_main);
        ViewCompat.setOnApplyWindowInsetsListener(findViewById(R.id.main), (v, insets) -> {
            Insets bars = insets.getInsets(WindowInsetsCompat.Type.systemBars());
            v.setPadding(bars.left, bars.top, bars.right, bars.bottom);
            return insets;
        });
    }
}`;
  const mainLayout=`<?xml version="1.0" encoding="utf-8"?>
<androidx.constraintlayout.widget.ConstraintLayout xmlns:android="http://schemas.android.com/apk/res/android"
    xmlns:app="http://schemas.android.com/apk/res-auto"
    android:id="@+id/main" android:layout_width="match_parent" android:layout_height="match_parent">
    <TextView android:layout_width="wrap_content" android:layout_height="wrap_content"
        android:text="@string/hello_world" app:layout_constraintTop_toTopOf="parent"
        app:layout_constraintBottom_toBottomOf="parent" app:layout_constraintStart_toStartOf="parent"
        app:layout_constraintEnd_toEndOf="parent" />
</androidx.constraintlayout.widget.ConstraintLayout>`;
  const defaults={activities:{'MainActivity.java':mainActivity},receivers:{},services:{},java_classes:{},layouts:{'activity_main.xml':mainLayout},values:{
    'strings.xml':'<resources>\n    <string name="app_name">Student App</string>\n    <string name="hello_world">Hello World!</string>\n</resources>',
    'colors.xml':'<resources>\n    <color name="purple_500">#6750A4</color>\n</resources>',
    'themes.xml':'<resources>\n    <style name="Theme.StudentApp" parent="Theme.MaterialComponents.DayNight.NoActionBar" />\n</resources>'},resources:{drawable:{},mipmap:{},raw:{},xml:{},anim:{},animator:{},menu:{},font:{}},manifest};
  const groups={activity:'activities',receiver:'receivers',service:'services',java_class:'java_classes',layout:'layouts',value:'values',drawable:'resources',mipmap:'resources',raw:'resources',xml:'resources',anim:'resources',animator:'resources',menu:'resources',font:'resources'};
  const labels={activity:'Activities',receiver:'Broadcast Receivers',service:'Services',java_class:'Java Classes',layout:'Layouts',value:'Values',drawable:'res/drawable',mipmap:'res/mipmap',raw:'res/raw',xml:'res/xml',anim:'res/anim',animator:'res/animator',menu:'res/menu',font:'res/font'};
  let project=clone(defaults),selected={type:'activity',name:'MainActivity.java'};
  function clone(x){return JSON.parse(JSON.stringify(x));}
  function bucket(type){return project.resources[type] || project[groups[type]];}
  function save(){if(isBinary(selected))return;if(selected.type==='manifest')project.manifest=editor.value;else bucket(selected.type)[selected.name]=editor.value;if(selected.type==='activity'&&selected.name==='MainActivity.java'){const match=editor.value.match(/^\s*package\s+([A-Za-z_][\w]*(?:\.[A-Za-z_][\w]*)+)\s*;/m);if(match)PACKAGE=match[1];}}
  function isBinary(file){return /\.(png|jpe?g|webp)$/i.test(file.name);}
  function content(){return selected.type==='manifest'?project.manifest:bucket(selected.type)[selected.name];}
  function select(type,name){save();selected={type,name};editor.value=isBinary(selected)?'[Image asset — upload a new image to replace this file]':content();editor.readOnly=isBinary(selected);title.textContent=(project.resources[selected.type]?'res/'+selected.type+'/':'')+name;renderTree();editor.focus();}
  function fileButton(type,name){const b=document.createElement('button');b.type='button';b.textContent=name;b.className=selected.type===type&&selected.name===name?'active':'';b.onclick=()=>select(type,name);return b;}
  function renderTree(){
    tree.replaceChildren();
    for(const type of ['activity','receiver','service','java_class','layout','value','drawable','mipmap','raw','xml','anim','animator','menu','font']){
      const section=document.createElement('div');section.className='android-file-group';section.innerHTML=`<b>${labels[type]}</b>`;
      Object.keys(bucket(type)).sort().forEach(name=>section.appendChild(fileButton(type,name)));tree.appendChild(section);
    }
    const config=document.createElement('div');config.className='android-file-group';config.innerHTML='<b>Configuration</b>';config.appendChild(fileButton('manifest','AndroidManifest.xml'));tree.appendChild(config);
    counts.textContent=`${Object.keys(project.activities).length}/10 activities · ${Object.keys(project.receivers).length}/10 receivers · ${Object.keys(project.services).length}/10 services · ${Object.keys(project.layouts).length}/15 layouts`;
    const protectedFile=selected.type==='manifest'||selected.type==='value'||selected.name==='MainActivity.java'||selected.name==='activity_main.xml';
    $('android-delete-file').disabled=protectedFile;$('android-rename-file').disabled=selected.type==='manifest'||selected.type==='value'||isBinary(selected);
  }
  function javaName(input){const n=(input||'').trim().replace(/\.java$/i,'');return /^[A-Z][A-Za-z0-9_]{0,49}$/.test(n)?n:'';}
  function xmlName(input){const n=(input||'').trim().replace(/\.xml$/i,'');return /^[a-z][a-z0-9_]{0,49}$/.test(n)?n:'';}
  function javaExists(file){return ['activities','receivers','services','java_classes'].some(group=>project[group][file]);}
  function addManifest(tag,name,extra=''){project.manifest=project.manifest.replace(/<\/application>/i,`        <${tag} android:name=".${name}"${extra} />\n    </application>`);}
  function removeManifest(tag,name){project.manifest=project.manifest.replace(new RegExp(`\\s*<${tag}[^>]*android:name=["']\\.${name}["'][^>]*/>\\s*`,'i'),'\n');}
  function addJava(type,promptText,example,template,tag,extra=''){
    save();const target=bucket(type),limit=type==='java_class'?20:10;if(Object.keys(target).length>=limit)return alert(`Maximum ${limit} ${labels[type].toLowerCase()} allowed.`);
    const name=javaName(prompt(promptText,example));if(!name)return alert('Use a Java class name beginning with a capital letter.');const file=name+'.java';if(javaExists(file))return alert('That Java filename already exists.');
    target[file]=template(name);if(tag)addManifest(tag,name,extra);selected={type,name:file};editor.value=target[file];title.textContent=file;renderTree();
  }
  const activity=name=>`package ${PACKAGE};\n\nimport android.os.Bundle;\nimport androidx.appcompat.app.AppCompatActivity;\n\npublic class ${name} extends AppCompatActivity {\n    @Override\n    protected void onCreate(Bundle savedInstanceState) {\n        super.onCreate(savedInstanceState);\n        setContentView(R.layout.activity_main);\n    }\n}`;
  const receiver=name=>`package ${PACKAGE};\n\nimport android.content.BroadcastReceiver;\nimport android.content.Context;\nimport android.content.Intent;\nimport android.widget.Toast;\n\npublic class ${name} extends BroadcastReceiver {\n    @Override\n    public void onReceive(Context context, Intent intent) {\n        Toast.makeText(context, "Broadcast received", Toast.LENGTH_SHORT).show();\n    }\n}`;
  const service=name=>`package ${PACKAGE};\n\nimport android.app.Service;\nimport android.content.Intent;\nimport android.os.IBinder;\n\npublic class ${name} extends Service {\n    @Override public IBinder onBind(Intent intent) { return null; }\n}`;
  const helper=name=>`package ${PACKAGE};\n\npublic class ${name} {\n    public static String message() { return "Hello from ${name}"; }\n}`;
  $('android-new-activity').onclick=()=>addJava('activity','Activity class name:','SecondActivity',activity,'activity',' android:exported="false"');
  $('android-new-receiver').onclick=()=>addJava('receiver','Receiver class name:','MyReceiver',receiver,'receiver',' android:exported="false"');
  $('android-new-service').onclick=()=>addJava('service','Service class name:','MyService',service,'service',' android:exported="false"');
  $('android-new-class').onclick=()=>addJava('java_class','Java class name:','Utility',helper);
  $('android-new-layout').onclick=()=>{save();if(Object.keys(project.layouts).length>=15)return alert('Maximum 15 layouts allowed.');const name=xmlName(prompt('Layout filename:','activity_second'));if(!name)return alert('Use lowercase letters, numbers and underscores.');const file=name+'.xml';if(project.layouts[file])return alert('That layout already exists.');project.layouts[file]=`<?xml version="1.0" encoding="utf-8"?>\n<LinearLayout xmlns:android="http://schemas.android.com/apk/res/android" android:layout_width="match_parent" android:layout_height="match_parent" android:gravity="center">\n    <TextView android:layout_width="wrap_content" android:layout_height="wrap_content" android:text="${name}" />\n</LinearLayout>`;select('layout',file);};
  $('android-new-resource').onclick=()=>{save();const folder=prompt('Resource folder: drawable, mipmap, raw, xml, anim, animator, menu or font','drawable');if(!folder||!project.resources[folder])return alert('Choose a supported resource folder.');const filename=xmlName(prompt('Resource XML filename (without .xml):','custom_background'));if(!filename)return alert('Use lowercase letters, numbers and underscores.');const file=filename+'.xml';if(project.resources[folder][file])return alert('That file already exists.');project.resources[folder][file]=folder==='drawable'?'<shape xmlns:android="http://schemas.android.com/apk/res/android" android:shape="rectangle">\n    <solid android:color="#6750A4" />\n</shape>':folder==='mipmap'?'<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">\n    <background android:drawable="@color/purple_500" />\n    <foreground android:drawable="@drawable/ic_launcher_foreground" />\n</adaptive-icon>':'<?xml version="1.0" encoding="utf-8"?>\n<resources />';select(folder,file);};
  // Both upload actions use the same resource transport already supported by the APK worker.
  // Only the dedicated launcher-icon action is allowed to edit the manifest automatically.
  let imageMode='drawable';
  $('android-upload-image').onclick=()=>{imageMode='drawable';$('android-image-file').click();};
  $('android-set-icon').onclick=()=>{imageMode='launcher';$('android-image-file').click();};
  function setLauncherIcon(name){
    const resource='@mipmap/'+name.replace(/\.(png|jpe?g|webp)$/i,'');
    const opening=project.manifest.match(/<application\b[^>]*>/i);
    if(!opening)throw Error('AndroidManifest.xml has no <application> tag. Add the tag before setting an app icon.');
    let tag=opening[0];
    if(/\bandroid:icon\s*=/.test(tag))tag=tag.replace(/\bandroid:icon\s*=\s*(["']).*?\1/i,'android:icon="'+resource+'"');
    else tag=tag.replace(/>$/,' android:icon="'+resource+'">');
    // Set both normal and round launcher icons. Other application attributes are untouched.
    if(/\bandroid:roundIcon\s*=/.test(tag))tag=tag.replace(/\bandroid:roundIcon\s*=\s*(["']).*?\1/i,'android:roundIcon="'+resource+'"');
    else tag=tag.replace(/>$/,' android:roundIcon="'+resource+'">');
    project.manifest=project.manifest.replace(opening[0],tag);
  }
  $('android-image-file').onchange=async e=>{
    const file=e.target.files[0];if(!file)return;
    const mode=imageMode;e.target.value='';save();
    const ext=(file.name.split('.').pop()||'').toLowerCase();
    if(!['png','jpg','jpeg','webp'].includes(ext)||!['image/png','image/jpeg','image/webp'].includes(file.type))return alert('Upload PNG, JPG, or WebP images only.');
    if(file.size>350000)return alert('Image must be under 350 KB. Resize or compress it first.');
    const folder=mode==='launcher'?'mipmap':'drawable';
    const suggested=mode==='launcher'?'ic_launcher':file.name.replace(/\.[^.]+$/,'').toLowerCase().replace(/[^a-z0-9_]/g,'_');
    const base=prompt(mode==='launcher'?'Launcher icon name (without extension):':'Image resource name (without extension):',suggested);
    if(base===null)return;
    if(!(/^[a-z][a-z0-9_]{0,49}$/).test(base))return alert('Use lowercase letters, numbers and underscores; start with a letter.');
    const name=base+'.'+ext;
    if(project.resources[folder][name]&&!confirm('Replace existing res/'+folder+'/'+name+'?'))return;
    if(mode==='launcher'&&!/<application\b[^>]*>/i.test(project.manifest))return alert('AndroidManifest.xml needs an <application> tag before the launcher icon can be set.');
    try{
      const encoded=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(String(reader.result).split(',')[1]);reader.onerror=reject;reader.readAsDataURL(file);});
      project.resources[folder][name]=encoded;
      if(mode==='launcher'){setLauncherIcon(name);/* Do not call select(): it saves the stale manifest editor text over the updated project.manifest. */selected={type:'manifest',name:'AndroidManifest.xml'};editor.value=project.manifest;editor.readOnly=false;title.textContent='AndroidManifest.xml';renderTree();status.textContent='Launcher icon set — rebuild APK';}
      else{select(folder,name);status.textContent='Image added to res/drawable';}
    }catch(error){alert('Unable to read image: '+error.message);}
  };
  $('android-rename-file').onclick=()=>{save();const old=selected.name;if(['activity','receiver','service','java_class'].includes(selected.type)){const name=javaName(prompt('New Java class name:',old.slice(0,-5)));if(!name)return;const file=name+'.java';if(javaExists(file)&&file!==old)return alert('That Java filename already exists.');const target=bucket(selected.type);target[file]=target[old].replace(new RegExp(`\\bpublic\\s+class\\s+${old.slice(0,-5)}\\b`),`public class ${name}`);delete target[old];if(selected.type!=='java_class')project.manifest=project.manifest.replace(new RegExp(`\\.${old.slice(0,-5)}(?=["'])`,'g'),'.'+name);selected.name=file;}else if(selected.type==='layout'||project.resources[selected.type]){const name=xmlName(prompt('New XML filename:',old.slice(0,-4)));if(!name)return;const file=name+'.xml';const target=bucket(selected.type);if(target[file]&&file!==old)return alert('That XML filename already exists.');target[file]=target[old];delete target[old];if(selected.type==='layout'){for(const group of ['activities','receivers','services','java_classes'])for(const key of Object.keys(project[group]))project[group][key]=project[group][key].replace(new RegExp(`R\\.layout\\.${old.slice(0,-4)}\\b`,'g'),'R.layout.'+name);}selected.name=file;}editor.value=content();editor.readOnly=false;title.textContent=selected.name;renderTree();};
  $('android-delete-file').onclick=()=>{save();if(!confirm(`Delete ${selected.name}?`))return;const old=selected.name;if(['activity','receiver','service'].includes(selected.type)){removeManifest({activity:'activity',receiver:'receiver',service:'service'}[selected.type],old.slice(0,-5));}delete bucket(selected.type)[old];selected={type:'activity',name:'MainActivity.java'};editor.value=content();editor.readOnly=false;title.textContent=selected.name;renderTree();};
  editor.onkeydown=e=>{if(e.key==='Tab'){e.preventDefault();editor.setRangeText('    ',editor.selectionStart,editor.selectionEnd,'end');}};
  $('android-reset').onclick=()=>{if(!confirm('Reset the complete Android project?'))return;project=clone(defaults);selected={type:'activity',name:'MainActivity.java'};editor.value=content();editor.readOnly=false;title.textContent=selected.name;status.textContent='Ready';output.textContent='Select Build APK when your project is ready.';download.hidden=qr.hidden=help.hidden=true;renderTree();};
  async function jsonResponse(response){const text=await response.text();try{return JSON.parse(text);}catch(_){throw Error(`Server returned ${response.status} instead of build data. Refresh the page; if it continues, check the web-service logs.`);}}
  const wait=ms=>new Promise(resolve=>setTimeout(resolve,ms));async function readJob(url){const started=Date.now();while(Date.now()-started<600000){await wait(3500+Math.random()*1500);const response=await fetch(url,{headers:{Accept:'application/json'},cache:'no-store'}),data=await jsonResponse(response);if(!response.ok||!data.ok)throw Error(data.error||'Unable to check build.');if(['completed','failed'].includes(data.status))return data;status.textContent=data.status==='queued'?`Queued · ${data.position||1}`:'Building…';}throw Error('Build timed out.');}
  build.onclick=async()=>{save();download.hidden=qr.hidden=help.hidden=true;qrImage.removeAttribute('src');build.disabled=true;status.textContent='Queuing…';output.textContent='Validating and uploading all project files…';try{const payload={app_name:$('android-app-name').value,experiment_id:$('android-experiment').value||null,...project},response=await fetch(root.dataset.buildUrl,{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':document.querySelector('meta[name="csrf-token"]').content},body:JSON.stringify(payload)}),queued=await jsonResponse(response);if(!response.ok||!queued.ok)throw Error(queued.error||'Build rejected.');const result=await readJob(queued.status_url);if(result.status==='failed'||!result.success)throw Error(result.error||result.output||'Build failed.');output.textContent=result.output;status.textContent='APK ready';download.href=result.download_url;download.hidden=false;if(result.qr_url){qrImage.src=result.qr_url;qrExpiry.textContent=`Secure link expires in ${result.qr_expires_minutes||30} minutes.`;qr.hidden=false;}help.hidden=false;}catch(error){status.textContent='Failed';output.textContent=error.message||'Build failed.';}finally{build.disabled=false;}};
  editor.value=content();renderTree();
})();
