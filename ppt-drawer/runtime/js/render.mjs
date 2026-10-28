import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import {createRequire} from 'node:module';
import {pathToFileURL,fileURLToPath} from 'node:url';
import {inflateRawSync} from 'node:zlib';
import os from 'node:os';

const styles={
  research_opening:{primary:'#002060',accent:'#007F8B',emphasis:'#C00000',width:960,height:540},
  red_academic:{primary:'#C00000',accent:'#C00000',emphasis:'#C00000',width:960,height:540},
  blue_layered:{primary:'#385D8A',accent:'#7F6000',emphasis:'#C00000',width:960,height:600},
  green_dual:{primary:'#2E663E',accent:'#8FAADC',emphasis:'#C00000',width:960,height:540},
  deep_mechanism:{primary:'#002060',accent:'#002060',emphasis:'#C00000',width:960,height:540},
  bluegray_charts:{primary:'#44546A',accent:'#4472C4',emphasis:'#C00000',width:960,height:540},
};
const layouts=new Set(['cover','title-content','two-column','evidence-grid','chart-table','process','summary']);
const aliases={L01:'cover',L02:'title-content',L03:'title-content',L04:'cover',L05:'evidence-grid',L06:'process',L07:'evidence-grid',L08:'two-column',L09:'two-column',L10:'two-column',L11:'evidence-grid',L12:'process',L13:'process',L14:'two-column',L15:'evidence-grid',L16:'evidence-grid',L17:'evidence-grid',L18:'chart-table',L19:'two-column',L20:'title-content',L21:'evidence-grid',L22:'summary',L23:'summary',L24:'summary',L25:'title-content',L26:'summary'};
const sha=bytes=>crypto.createHash('sha256').update(bytes).digest('hex');

async function artifactTool(){
  const local=createRequire(import.meta.url);
  const candidates=[process.env.PPT_DRAWER_NODE_MODULES,process.env.RUNTIME_NODE_MODULES,process.env.CODEX_PRIMARY_RUNTIME_NODE_MODULES,...(process.env.NODE_PATH||'').split(path.delimiter),path.resolve(path.dirname(process.execPath),'../node_modules')].filter(Boolean);
  const load=async(entry,moduleRoot)=>{process.env.RUNTIME_NODE_MODULES=moduleRoot;return import(pathToFileURL(entry).href);};
  for(const dir of candidates){
    try{
      const requireFromRuntime=createRequire(path.join(path.resolve(dir),'__runtime__.cjs'));
      return await load(requireFromRuntime.resolve('@oai/artifact-tool'),path.resolve(dir));
    }catch(error){if(dir===process.env.PPT_DRAWER_NODE_MODULES)throw new Error(`Cannot resolve @oai/artifact-tool from explicit PPT_DRAWER_NODE_MODULES: ${dir}`,{cause:error});}
  }
  try{
    const entry=local.resolve('@oai/artifact-tool');let moduleRoot=path.dirname(entry);
    while(path.basename(moduleRoot)!=='node_modules'&&path.dirname(moduleRoot)!==moduleRoot)moduleRoot=path.dirname(moduleRoot);
    return await load(entry,moduleRoot);
  }catch{}
  throw new Error('Cannot resolve @oai/artifact-tool; set PPT_DRAWER_NODE_MODULES to the bundled Node packages directory.');
}

async function validationRuntime(){
  const candidates=[process.env.PPT_DRAWER_PRESENTATIONS_SKILL];
  const home=process.env.CODEX_HOME||path.join(os.homedir(),'.codex');
  const cache=path.join(home,'plugins/cache/openai-primary-runtime/presentations');
  try{for(const version of (await fs.readdir(cache)).sort().reverse())candidates.push(path.join(cache,version,'skills/presentations'));}catch{}
  let skill;
  for(const candidate of candidates.filter(Boolean)){try{await fs.access(path.join(candidate,'container_tools/artifact_tool_utils.mjs'));skill=candidate;break;}catch{}}
  if(!skill)throw new Error('Presentation validation helpers unavailable; set PPT_DRAWER_PRESENTATIONS_SKILL to the installed Presentations skill directory.');
  const python=process.env.PPT_DRAWER_PYTHON||path.resolve(path.dirname(process.execPath),'../../python',process.platform==='win32'?'python.exe':'bin/python3');
  await fs.access(python);
  return {skill,python};
}

function validatePlan(plan,stage){
  if(plan.version!==1||!Array.isArray(plan.slides)||!plan.slides.length)throw new Error('Page plan must have version 1 and nonempty slides.');
  if(!['sample','full'].includes(stage))throw new Error('stage must be sample or full');
  const ids=new Set();
  for(const s of plan.slides){
    if(typeof s.id!=='string'||!s.id||ids.has(s.id))throw new Error('Every slide needs a unique id.');ids.add(s.id);
    if(typeof s.title!=='string'||!s.title.trim())throw new Error(`Slide ${s.id} needs title.`);
    if(!layouts.has(aliases[s.layout]||s.layout))throw new Error(`Unsupported layout ${s.layout}`);
    if(!Array.isArray(s.blocks))throw new Error(`Slide ${s.id} needs blocks.`);
    if(s.blocks.length>6)throw new Error(`Slide ${s.id} is too dense; split it into pages.`);
    if((aliases[s.layout]||s.layout)==='chart-table'&&s.blocks.length>2)throw new Error('chart-table layout accepts at most two evidence blocks; move additional content to another page.');
    if(s.template_slide!==undefined&&(!Number.isSafeInteger(s.template_slide)||s.template_slide<1))throw new Error('template_slide must be a positive 1-based source slide number.');
    if(s.template_preserve_names!==undefined&&(!Array.isArray(s.template_preserve_names)||s.template_preserve_names.some(n=>typeof n!=='string'||!n)))throw new Error('template_preserve_names must contain source object names.');
    if(s.template_preserve_ids!==undefined&&(!Array.isArray(s.template_preserve_ids)||s.template_preserve_ids.some(n=>typeof n!=='string'||!n)))throw new Error('template_preserve_ids must contain source object IDs as strings.');
    for(const b of s.blocks){
      if(!['text','image','chart','table','process'].includes(b.type))throw new Error(`Unsupported block type ${b.type}`);
      if(b.type==='chart'){
        if(!['bar','line'].includes(b.chart_type)||!Array.isArray(b.categories)||!b.categories.length||!Array.isArray(b.series)||!b.series.length)throw new Error('Chart needs type, categories and series.');
        for(const series of b.series)if(!Array.isArray(series.values)||series.values.length!==b.categories.length||series.values.some(v=>typeof v!=='number'||!Number.isFinite(v)))throw new Error('Chart categories and values dimensions must match with finite numeric values.');
      }
      if(b.type==='table'&&(!Array.isArray(b.headers)||!b.headers.length||!Array.isArray(b.rows)||b.rows.some(r=>!Array.isArray(r)||r.length!==b.headers.length)))throw new Error('Table row dimensions must match headers.');
      if(b.type==='process'&&(!Array.isArray(b.steps)||!b.steps.length))throw new Error('Process needs steps.');
      if(b.type==='image'&&typeof b.path!=='string')throw new Error('Image needs local path.');
    }
  }
  let selected=plan.slides;
  if(stage==='sample'){
    const sample=plan.sample_slide_ids||plan.slides.slice(0,3).map(s=>s.id);
    if(!Array.isArray(sample)||new Set(sample).size!==sample.length||sample.length!==Math.min(3,plan.slides.length)||sample.some(id=>!ids.has(id)))throw new Error('sample_slide_ids must select three unique existing slides (or all slides for shorter plans).');
    selected=sample.map(id=>plan.slides.find(s=>s.id===id));
  }
  return selected;
}

function zipEntries(bytes){
  const lowerBound=Math.max(0,bytes.length-65557);
  let end=bytes.length-22;while(end>=lowerBound&&bytes.readUInt32LE(end)!==0x06054b50)end--;
  if(end<lowerBound)throw new Error('Invalid PPTX ZIP: end record missing.');
  let offset=bytes.readUInt32LE(end+16);const count=bytes.readUInt16LE(end+10),entries=new Map();
  for(let i=0;i<count;i++){
    if(bytes.readUInt32LE(offset)!==0x02014b50)throw new Error('Invalid PPTX ZIP central directory.');
    const method=bytes.readUInt16LE(offset+10),size=bytes.readUInt32LE(offset+20),nameLen=bytes.readUInt16LE(offset+28),extraLen=bytes.readUInt16LE(offset+30),commentLen=bytes.readUInt16LE(offset+32),local=bytes.readUInt32LE(offset+42);
    const name=bytes.subarray(offset+46,offset+46+nameLen).toString('utf8');
    const start=local+30+bytes.readUInt16LE(local+26)+bytes.readUInt16LE(local+28),compressed=bytes.subarray(start,start+size);
    entries.set(name,method===8?inflateRawSync(compressed):compressed);offset+=46+nameLen+extraLen+commentLen;
  }
  return entries;
}

function inspectPptx(bytes){
  const entries=zipEntries(bytes),p=entries.get('ppt/presentation.xml')?.toString()||'';
  if(!entries.has('[Content_Types].xml')||!p)throw new Error('Invalid PPTX package structure.');
  const slideParts=[...entries].filter(([n])=>/^ppt\/slides\/slide\d+\.xml$/.test(n));
  const xml=slideParts.map(([,b])=>b.toString()).join('\n');
  const size=p.match(/<p:sldSz\b[^>]*>/)?.[0],cx=size?.match(/\bcx="(\d+)"/)?.[1],cy=size?.match(/\bcy="(\d+)"/)?.[1];
  return {entries,native:{textboxes:(xml.match(/<p:sp[\s>]/g)||[]).length,charts:[...entries.keys()].filter(n=>/^ppt\/(?:.*\/)?charts\/chart\d+\.xml$/.test(n)).length,tables:(xml.match(/<a:tbl[\s>]/g)||[]).length,images:(xml.match(/<p:pic[\s>]/g)||[]).length,embedded_workbooks:[...entries.keys()].filter(n=>/^ppt\/embeddings\/.*\.xlsx$/.test(n)).length},slide_count:slideParts.length,slide_size:cx&&cy?{width:Number(cx)/9525,height:Number(cy)/9525}:null};
}

async function cloneMappedSlide(presentation,sources,page){
  if(page.template_slide>sources.length)throw new Error(`Source template slide ${page.template_slide} does not exist.`);
  const slide=sources[page.template_slide-1].duplicate();
  const slideIndex=presentation.slides.items.findIndex(s=>s.id===slide.id);
  const snapshot=await presentation.inspect({kind:'shape,textbox,image,table,chart',limit:10000,maxChars:4000000});
  if(snapshot.truncated)throw new Error('Source template page inspection was truncated; simplify the template page.');
  const records=snapshot.ndjson.split('\n').filter(Boolean).map(line=>JSON.parse(line)).filter(r=>r.slideIndex===slideIndex&&/^(sh|im|tb|ch)\//.test(r.id||'')).map(r=>({...r,source_id:String(presentation.resolve(r.id).id)}));
  const wanted=new Set();
  for(const name of page.template_preserve_names||[]){const matches=records.filter(r=>r.name===name);if(!matches.length)throw new Error(`Source template object name not found: ${name}`);for(const r of matches)wanted.add(r.id);}
  for(const id of page.template_preserve_ids||[]){const r=records.find(r=>r.source_id===id);if(!r)throw new Error(`Source template object ID not found: ${id}`);wanted.add(r.id);}
  const targets={};
  for(const [key,name,id] of [['title',page.template_title_name,page.template_title_id],['takeaway',page.template_takeaway_name,page.template_takeaway_id],['number',page.template_page_number_name,page.template_page_number_id]]){
    if(!name&&id===undefined)continue;
    const matches=records.filter(r=>id!==undefined?r.source_id===String(id):r.name===name);
    if(matches.length!==1||matches[0].kind!=='textbox')throw new Error(`Mapped ${key} must identify one editable source textbox; use a source object ID when names repeat: ${id??name}`);
    wanted.add(matches[0].id);
    targets[key]={shape:presentation.resolve(matches[0].id),oldText:matches[0].text||''};
  }
  const remove=records.filter(r=>!wanted.has(r.id)).map(r=>r.id);
  if(remove.length)presentation.delete(remove);
  return {slide,targets,mapping:{slide_id:page.id,source_slide:page.template_slide,preserved_objects:records.filter(r=>wanted.has(r.id)).map(r=>({source_id:r.source_id,name:r.name}))}};
}

function replaceMappedText(target,value){
  if(target.oldText)target.shape.text.replace(target.oldText,String(value||''));
  else target.shape.text=String(value||'');
}

function text(slide,name,value,box,style={},geometry){
  const shape=slide.shapes.add({name,geometry:geometry||'textbox',position:box,fill:style.fill||'none',line:{fill:style.line||'none',width:style.line?1:0}});
  shape.text=Array.isArray(value)?value:String(value??'');shape.text.style={typeface:style.fontFamily||'Microsoft YaHei',fontSize:style.fontSize||22,color:style.color||'#17233B',bold:!!style.bold,...(style.align?{alignment:style.align}:{})};return shape;
}
function boxesFor(layout,count,area){
  if(!count)return[];
  if(layout==='chart-table'&&count>=2)return[{left:area.left,top:area.top,width:area.width,height:area.height*.57},{left:area.left,top:area.top+area.height*.62,width:area.width,height:area.height*.38},...Array.from({length:count-2},()=>({...area}))];
  const columns=layout==='two-column'?Math.min(count,2):layout==='evidence-grid'?Math.min(count,3):count>2?2:1;
  const rows=Math.ceil(count/columns),gap=20,w=(area.width-gap*(columns-1))/columns,h=(area.height-gap*(rows-1))/rows;
  return Array.from({length:count},(_,i)=>({left:area.left+(i%columns)*(w+gap),top:area.top+Math.floor(i/columns)*(h+gap),width:w,height:h}));
}

async function drawBlock(slide,block,box,style,index,baseDir,geometry){
  const prefix=`block-${index}`;
  geometry.push({name:prefix,...box});
  if(block.title&&block.type!=='chart'){text(slide,prefix+'-title',block.title,{...box,height:28},{fontSize:19,bold:true,color:style.primary});box={...box,top:box.top+35,height:box.height-35};}
  if(block.type==='text'){
    const value=block.text??(block.items||[]).map(x=>({bulletCharacter:'•',marginLeft:228600,indent:-114300,spaceAfter:800,runs:[String(x)]}));
    text(slide,prefix,value,box,{fontSize:box.height<100?18:23});
  }else if(block.type==='image'){
    const imagePath=path.isAbsolute(block.path)?block.path:path.resolve(baseDir,block.path),imageBytes=await fs.readFile(imagePath);
    const contentTypes={'.png':'image/png','.jpg':'image/jpeg','.jpeg':'image/jpeg','.webp':'image/webp','.gif':'image/gif','.svg':'image/svg+xml','.tif':'image/tiff','.tiff':'image/tiff'};
    const contentType=contentTypes[path.extname(imagePath).toLowerCase()];
    if(!contentType||!imageBytes.length)throw new Error(`Unsupported or empty image input: ${imagePath}`);
    const caption=block.caption||'';slide.images.add({blob:new Uint8Array(imageBytes),contentType,fit:'contain',position:{...box,height:box.height-(caption?32:0)},alt:caption||path.basename(imagePath)});
    if(caption)text(slide,prefix+'-caption',caption,{left:box.left,top:box.top+box.height-28,width:box.width,height:28},{fontSize:14,color:'#536178'});
  }else if(block.type==='chart'){
    const chart=slide.charts.add(block.chart_type,{name:prefix,position:box,categories:block.categories.map(String),series:block.series.map((s,i)=>({name:s.name||`Series ${i+1}`,values:s.values,fill:[style.primary,style.emphasis,'#8FAADC','#7F6000'][i%4]})),hasLegend:block.series.length>1,title:block.title||'',xAxis:{textStyle:{fontSize:15}},yAxis:{textStyle:{fontSize:15},majorGridlines:{fill:'#D9DFE8',width:1}},dataLabels:{showValue:block.show_values!==false,position:block.chart_type==='line'?'top':'outEnd'}});
    for(const target of [chart.xAxis?.textStyle,chart.yAxis?.textStyle,chart.legend?.textStyle,chart.dataLabels?.textStyle,...(block.title?[chart.titleTextStyle]:[])])if(target)target.typeface='Microsoft YaHei';
  }else if(block.type==='table'){
    const values=[block.headers,...block.rows].map(r=>r.map(v=>String(v??''))),table=slide.tables.add({rows:values.length,columns:values[0].length,left:box.left,top:box.top,width:box.width,height:box.height,values});
    table.borders.assign({fill:'#B9C4D4',width:0.6});
    table.cells.block({row:0,column:0,rowCount:values.length,columnCount:values[0].length}).assign({textStyle:{typeface:'Microsoft YaHei',fontSize:Math.min(20,Math.max(13,box.height/values.length*.5)),color:'#17233B'},fill:'#FFFFFF'});
    table.cells.block({row:0,column:0,rowCount:1,columnCount:values[0].length}).assign({fill:style.primary,textStyle:{bold:true,color:'#FFFFFF'}});
  }else if(block.type==='process'){
    const n=block.steps.length,gap=24,w=(box.width-gap*(n-1))/n;
    if(w<100)throw new Error('Process is too dense; split the page or use fewer steps.');
    block.steps.forEach((step,i)=>{
      const x=box.left+i*(w+gap),y=box.top+box.height*.22;
      text(slide,`${prefix}-step-${i}`,`${i+1}  ${step.title}`,{left:x,top:y,width:w,height:52},{fontSize:20,bold:true,color:'#FFFFFF',fill:style.primary},'rect');
      text(slide,`${prefix}-description-${i}`,step.text||'',{left:x,top:y+62,width:w,height:Math.max(60,box.height*.45)},{fontSize:18});
      if(i<n-1)text(slide,`${prefix}-arrow-${i}`,'›',{left:x+w+3,top:y+8,width:20,height:30},{fontSize:28,bold:true,color:style.primary});
    });
  }
}

export async function runRenderer(options){
  if(!options.plan||!options.output)throw new Error('Usage: render.mjs --plan <json> --output <dir> --stage sample|full');
  const planPath=path.resolve(options.plan),raw=await fs.readFile(planPath),plan=JSON.parse(raw.toString('utf8').replace(/^\uFEFF/,'')),stage=options.stage||'sample';
  const selected=validatePlan(plan,stage),output=path.resolve(options.output);
  const workspace=path.dirname(output);
  if(workspace===output)throw new Error('Output must be a presentation subdirectory, not a filesystem root.');
  try{await fs.access(path.join(output,'deck.pptx'));throw new Error('Output deck already exists; select a new output directory.');}catch(e){if(e.code!=='ENOENT')throw e;}
  const {Presentation,PresentationFile,FileBlob}=await artifactTool();
  let style=typeof plan.style==='object'?{...styles.deep_mechanism,...plan.style}:styles[plan.style||'deep_mechanism'];
  if(!style)throw new Error(`Unknown style ${plan.style}`);
  const templatePath=options.template||plan.template,warnings=[],geometry=[],mappings=[],outputSlides=[],inputAssets=[];
  if(!templatePath&&selected.some(s=>s.template_slide))throw new Error('template_slide mapping requires a template PPTX.');
  let presentation,sourceSlides=[];
  if(templatePath){
    const absolute=path.resolve(path.dirname(planPath),templatePath);
    if(path.extname(absolute).toLowerCase()!=='.pptx')throw new Error('Native template mapping needs PPTX; convert a legacy PPT or rebuild a PDF reference before rendering.');
    const templateBytes=await fs.readFile(absolute),native=inspectPptx(templateBytes);
    inputAssets.push({kind:'template',path:absolute,sha256:sha(templateBytes)});
    if(!native.slide_size)throw new Error('Template slide dimensions are missing.');
    presentation=await PresentationFile.importPptx(await FileBlob.load(absolute));
    sourceSlides=[...presentation.slides.items];
    style={...style,...native.slide_size};
    if(selected.some(s=>!s.template_slide))warnings.push('Some pages use imported theme and masters only. Hand-placed source headers/logos are not automatically reused; use explicit template_slide/object-name mappings for native source-page reuse.');
    if(selected.some(s=>s.template_slide))warnings.push('Mapped template pages retain only explicitly selected source objects and title styles. New body content is rebuilt; review exact fidelity against the reference.');
  }else presentation=Presentation.create({slideSize:{width:style.width,height:style.height}});
  const w=style.width,h=style.height;
  if(!Number.isFinite(w)||!Number.isFinite(h)||w<320||h<240||w>10000||h>10000)throw new Error('Slide dimensions must be finite pixels in a supported presentation range.');
  if(!templatePath)presentation.theme.colorScheme={name:'PPT Drawer',themeColors:{accent1:style.primary,accent2:style.emphasis,accent3:style.accent,accent4:'#8FAADC',accent5:'#7F6000',accent6:'#2E663E',bg1:'#FFFFFF',bg2:'#F3F6FA',tx1:'#17233B',tx2:'#536178',dk1:'#000000',dk2:style.primary,lt1:'#FFFFFF',lt2:'#F3F6FA',hlink:style.primary,folHlink:style.emphasis}};
  for(const block of selected.flatMap(s=>s.blocks).filter(b=>b.type==='image')){
    const imagePath=path.isAbsolute(block.path)?block.path:path.resolve(path.dirname(planPath),block.path);
    if(!inputAssets.some(a=>a.path===imagePath))inputAssets.push({kind:'image',path:imagePath,sha256:sha(await fs.readFile(imagePath))});
  }
  await fs.mkdir(path.join(output,'previews'),{recursive:true});
  for(let i=0;i<selected.length;i++){
    const page=selected[i],mapped=page.template_slide?await cloneMappedSlide(presentation,sourceSlides,page):null,slide=mapped?.slide||presentation.slides.add();
    outputSlides.push('sl/'+slide.id);if(mapped)mappings.push(mapped.mapping);else slide.background.fill='#FFFFFF';
    const layout=aliases[page.layout]||page.layout,cover=layout==='cover';
    if(mapped?.targets.title)replaceMappedText(mapped.targets.title,page.title);
    else text(slide,'page-title',page.title,{left:42,top:cover?95:18,width:w-84,height:cover?104:52},{fontSize:cover?36:29,bold:true,color:style.primary});
    if(!cover&&!mapped)text(slide,'title-rule','',{left:34,top:76,width:w-68,height:2},{fill:style.primary},'rect');
    const area={left:44,top:cover?235:103,width:w-88,height:h-(cover?340:202)},boxes=boxesFor(layout,page.blocks.length,area);
    for(let b=0;b<page.blocks.length;b++)await drawBlock(slide,page.blocks[b],boxes[b],style,b,path.dirname(planPath),geometry);
    if(mapped?.targets.takeaway)replaceMappedText(mapped.targets.takeaway,page.takeaway);
    else if(page.takeaway)text(slide,'page-takeaway',page.takeaway,{left:44,top:h-77,width:w-88,height:38},{fontSize:19,bold:true,color:style.emphasis});
    if(mapped?.targets.number)replaceMappedText(mapped.targets.number,String(i+1));
    else text(slide,'page-number',String(i+1),{left:w-52,top:h-30,width:24,height:20},{fontSize:12,color:'#536178'});
    slide.speakerNotes.text=JSON.stringify({page_id:page.id,source_ids:page.source_ids||[],block_sources:page.blocks.map(b=>b.source_id).filter(Boolean)},null,2);
  }
  presentation.slides.keep(outputSlides);presentation.slides.reorder(outputSlides);
  const staging=await fs.mkdtemp(path.join(workspace,'.ppt-drawer-build-'));
  const draft=path.join(staging,'candidate.pptx');await(await PresentationFile.exportPptx(presentation)).save(draft);
  const finalPath=path.join(output,'deck.pptx'),runtime=await validationRuntime();
  const {finalizePresentation}=await import(pathToFileURL(path.join(runtime.skill,'container_tools/artifact_tool_utils.mjs')).href);
  const tableOwners=selected.flatMap((s,i)=>s.blocks.some(b=>b.type==='table')?[i+1]:[]),chartOwners=selected.flatMap((s,i)=>s.blocks.some(b=>b.type==='chart')?[i+1]:[]);
  await finalizePresentation({
    workspaceDir:workspace,candidatePath:draft,finalPath,pythonExecutable:runtime.python,
    integrityValidatorPath:path.join(runtime.skill,'container_tools/inspect_presentation_package_integrity.py'),
    layoutValidatorPath:path.join(runtime.skill,'container_tools/inspect_presentation_layout_geometry.py'),
    layoutArgs:['--expected-slide-size-emu',`${Math.round(w*9525)},${Math.round(h*9525)}`,'--validate-heading-fit','--validate-bullet-geometry',...tableOwners.flatMap(n=>['--require-native-table-slide',String(n)])],
    explicitTotalSlideCount:selected.length,requiredNativeTableOwnerSlides:tableOwners,
    requiredNativeChartOwnerSlides:chartOwners,materializeLiteralChartWorkbooks:true,
    fontPolicy:templatePath?undefined:{basis:'design',families:['Microsoft YaHei']},
    verifyArtifactToolImport:true,receiptPath:path.join(staging,'validation.json'),
  });
  const previews=[];
  const finalized=await PresentationFile.importPptx(await FileBlob.load(finalPath));
  for(let i=0;i<finalized.slides.items.length;i++){
    const relative=`previews/slide-${String(i+1).padStart(3,'0')}.png`,blob=await finalized.export({slide:finalized.slides.items[i],format:'png',scale:1.5});
    await fs.writeFile(path.join(output,relative),new Uint8Array(await blob.arrayBuffer()));previews.push(relative);
  }
  const inspection=inspectPptx(await fs.readFile(finalPath)),bad=geometry.filter(b=>b.left<0||b.top<0||b.left+b.width>w+1||b.top+b.height>h+1||b.width<=0||b.height<=0);
  if(inspection.slide_count!==selected.length)throw new Error('PPTX physical slide count mismatch.');
  const changedAssets=[];
  for(const asset of inputAssets)if(sha(await fs.readFile(asset.path))!==asset.sha256)changedAssets.push(asset.path);
  const media_entries=[...inspection.entries].filter(([part])=>part.startsWith('ppt/media/')).map(([part,bytes])=>({part,bytes:bytes.length,sha256:sha(bytes)}));
  const emptyMedia=media_entries.filter(entry=>!entry.bytes).map(entry=>entry.part);
  const content_check=[...inspection.entries].filter(([n])=>/^ppt\/slides\/slide\d+\.xml$/.test(n)).map(([part,bytes])=>({part,text:[...bytes.toString().matchAll(/<a:t(?:\s[^>]*)?>([\s\S]*?)<\/a:t>/g)].map(m=>m[1]).join('\n')}));
  const report={version:1,stage,slide_ids:selected.map(s=>s.id),slide_count:selected.length,plan_sha256:sha(raw),slide_size:{width:w,height:h},native:inspection.native,previews,warnings,input_assets:inputAssets,media_entries,validation_receipt:path.join(staging,'validation.json'),errors:[...bad.map(b=>`Off-canvas block ${b.name}`),...changedAssets.map(p=>`Input asset changed during rendering: ${p}`),...emptyMedia.map(p=>`Empty embedded media: ${p}`)],checks:{package_integrity:'passed',previews:'passed',geometry:bad.length?'failed':'passed',input_assets:changedAssets.length?'failed':'passed',embedded_media:emptyMedia.length?'failed':'passed',powerpoint_application:'not_tested'},content_check,template:templatePath?{path:path.resolve(path.dirname(planPath),templatePath),sha256:inputAssets.find(a=>a.kind==='template')?.sha256,mode:mappings.length===selected.length?'mapped_source_slides':mappings.length?'mixed':'imported_theme_and_masters',source_slide_objects_preserved:mappings.length>0,mappings}:null};
  await fs.writeFile(path.join(output,'render-report.json'),JSON.stringify(report,null,2));
  if(report.errors.length)throw new Error(report.errors.join('; '));
  return report;
}

function parseArguments(args){const options={};for(let i=0;i<args.length;i+=2){if(!['--plan','--output','--stage','--template'].includes(args[i])||!args[i+1])throw new Error(`Unknown or missing argument ${args[i]}`);options[args[i].slice(2)]=args[i+1];}return options;}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url))runRenderer(parseArguments(process.argv.slice(2))).then(report=>console.log(JSON.stringify({output:path.resolve(parseArguments(process.argv.slice(2)).output),...report}))).catch(error=>{console.error(error.message);process.exitCode=1;});
