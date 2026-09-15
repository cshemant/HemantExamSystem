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
    'themes.xml':'<resources>\n    <style name="Theme.StudentApp" parent="Theme.MaterialComponents.DayNight.NoActionBar" />\n</resources>'},manifest};
  const groups={activity:'activities',receiver:'receivers',service:'services',java_class:'java_classes',layout:'layouts',value:'values'};
  const labels={activity:'Activities',receiver:'Broadcast Receivers',service:'Services',java_class:'Java Classes',layout:'Layouts',value:'Values'};
  let project=clone(defaults),selected={type:'activity',name:'MainActivity.java'};
  function clone(x){return JSON.parse(JSON.stringify(x));}
  function bucket(type){return project[groups[type]];}
  function save(){if(selected.type==='manifest')project.manifest=editor.value;else bucket(selected.type)[selected.name]=editor.value;if(selected.type==='activity'&&selected.name==='MainActivity.java'){const match=editor.value.match(/^\s*package\s+([A-Za-z_][\w]*(?:\.[A-Za-z_][\w]*)+)\s*;/m);if(match)PACKAGE=match[1];}}
  function content(){return selected.type==='manifest'?project.manifest:bucket(selected.type)[selected.name];}
  function select(type,name){save();selected={type,name};editor.value=content();title.textContent=name;renderTree();editor.focus();}
  function fileButton(type,name){const b=document.createElement('button');b.type='button';b.textContent=name;b.className=selected.type===type&&selected.name===name?'active':'';b.onclick=()=>select(type,name);return b;}
  function renderTree(){
    tree.replaceChildren();
    for(const type of ['activity','receiver','service','java_class','layout','value']){
      const section=document.createElement('div');section.className='android-file-group';section.innerHTML=`<b>${labels[type]}</b>`;
      Object.keys(bucket(type)).sort().forEach(name=>section.appendChild(fileButton(type,name)));tree.appendChild(section);
    }
    const config=document.createElement('div');config.className='android-file-group';config.innerHTML='<b>Configuration</b>';config.appendChild(fileButton('manifest','AndroidManifest.xml'));tree.appendChild(config);
    counts.textContent=`${Object.keys(project.activities).length}/10 activities · ${Object.keys(project.receivers).length}/10 receivers · ${Object.keys(project.services).length}/10 services · ${Object.keys(project.layouts).length}/15 layouts`;
    const protectedFile=selected.type==='manifest'||selected.type==='value'||selected.name==='MainActivity.java'||selected.name==='activity_main.xml';
    $('android-delete-file').disabled=protectedFile;$('android-rename-file').disabled=selected.type==='manifest'||selected.type==='value';
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
  $('android-rename-file').onclick=()=>{save();const old=selected.name;if(['activity','receiver','service','java_class'].includes(selected.type)){const name=javaName(prompt('New Java class name:',old.slice(0,-5)));if(!name)return;const file=name+'.java';if(javaExists(file)&&file!==old)return alert('That Java filename already exists.');const target=bucket(selected.type);target[file]=target[old].replace(new RegExp(`\\bpublic\\s+class\\s+${old.slice(0,-5)}\\b`),`public class ${name}`);delete target[old];if(selected.type!=='java_class')project.manifest=project.manifest.replace(new RegExp(`\\.${old.slice(0,-5)}(?=["'])`,'g'),'.'+name);selected.name=file;}else if(selected.type==='layout'){const name=xmlName(prompt('New layout filename:',old.slice(0,-4)));if(!name)return;const file=name+'.xml';if(project.layouts[file]&&file!==old)return alert('That layout already exists.');project.layouts[file]=project.layouts[old];delete project.layouts[old];for(const group of Object.values(groups).slice(0,4))for(const key of Object.keys(project[group]))project[group][key]=project[group][key].replace(new RegExp(`R\\.layout\\.${old.slice(0,-4)}\\b`,'g'),'R.layout.'+name);selected.name=file;}editor.value=content();title.textContent=selected.name;renderTree();};
  $('android-delete-file').onclick=()=>{save();if(!confirm(`Delete ${selected.name}?`))return;const old=selected.name;if(['activity','receiver','service'].includes(selected.type)){removeManifest({activity:'activity',receiver:'receiver',service:'service'}[selected.type],old.slice(0,-5));}delete bucket(selected.type)[old];selected={type:'activity',name:'MainActivity.java'};editor.value=content();title.textContent=selected.name;renderTree();};
  editor.onkeydown=e=>{if(e.key==='Tab'){e.preventDefault();editor.setRangeText('    ',editor.selectionStart,editor.selectionEnd,'end');}};
  $('android-reset').onclick=()=>{if(!confirm('Reset the complete Android project?'))return;project=clone(defaults);selected={type:'activity',name:'MainActivity.java'};editor.value=content();title.textContent=selected.name;status.textContent='Ready';output.textContent='Select Build APK when your project is ready.';download.hidden=qr.hidden=help.hidden=true;renderTree();};
  async function jsonResponse(response){const text=await response.text();try{return JSON.parse(text);}catch(_){throw Error(`Server returned ${response.status} instead of build data. Refresh the page; if it continues, check the web-service logs.`);}}
  const wait=ms=>new Promise(resolve=>setTimeout(resolve,ms));async function readJob(url){const started=Date.now();while(Date.now()-started<600000){await wait(3500+Math.random()*1500);const response=await fetch(url,{headers:{Accept:'application/json'},cache:'no-store'}),data=await jsonResponse(response);if(!response.ok||!data.ok)throw Error(data.error||'Unable to check build.');if(['completed','failed'].includes(data.status))return data;status.textContent=data.status==='queued'?`Queued · ${data.position||1}`:'Building…';}throw Error('Build timed out.');}
  build.onclick=async()=>{save();download.hidden=qr.hidden=help.hidden=true;qrImage.removeAttribute('src');build.disabled=true;status.textContent='Queuing…';output.textContent='Validating and uploading all project files…';try{const payload={app_name:$('android-app-name').value,...project},response=await fetch(root.dataset.buildUrl,{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':document.querySelector('meta[name="csrf-token"]').content},body:JSON.stringify(payload)}),queued=await jsonResponse(response);if(!response.ok||!queued.ok)throw Error(queued.error||'Build rejected.');const result=await readJob(queued.status_url);if(result.status==='failed'||!result.success)throw Error(result.error||result.output||'Build failed.');output.textContent=result.output;status.textContent='APK ready';download.href=result.download_url;download.hidden=false;if(result.qr_url){qrImage.src=result.qr_url;qrExpiry.textContent=`Secure link expires in ${result.qr_expires_minutes||30} minutes.`;qr.hidden=false;}help.hidden=false;}catch(error){status.textContent='Failed';output.textContent=error.message||'Build failed.';}finally{build.disabled=false;}};
  editor.value=content();renderTree();
})();
