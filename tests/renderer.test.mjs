import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {createHash} from 'node:crypto';

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const cli=path.join(root,'ppt-drawer/runtime/js/render.mjs');
const {runRenderer}=await import(pathToFileURL(cli).href);
const fixture={version:1,title:'演示数据：材料汇报',style:'blue_layered',slides:[
  {id:'context',title:'研究问题与证据',layout:'two-column',takeaway:'该页仅用于验证制作能力',source_ids:['paper'],blocks:[{type:'text',text:'研究对象与研究问题'},{type:'text',items:['证据来自指定材料','保留来源与单位']}]},
  {id:'data',title:'演示数据与参数',layout:'chart-table',takeaway:'演示数值不代表真实研究结果',source_ids:['data'],blocks:[{type:'chart',chart_type:'bar',categories:['对照','目标'],series:[{name:'演示值',values:[12,18]}],source_id:'data'},{type:'table',headers:['样品','演示值'],rows:[['对照',12],['目标',18]],source_id:'data'}]},
  {id:'route',title:'验证路线',layout:'process',takeaway:'过程与结论分别表达',source_ids:['paper'],blocks:[{type:'process',steps:[{title:'材料',text:'读取指定来源'},{title:'方案',text:'明确每页证据'},{title:'制作',text:'保留原生对象'}]}]},
  {id:'closing',title:'总结',layout:'summary',takeaway:'完整稿包含第四页',source_ids:['paper'],blocks:[{type:'text',text:'这是技术验证内容'}]}
],sample_slide_ids:['context','data','route']};

test('public renderer rejects inconsistent chart data before creating a deck',async()=>{
  const dir=await fs.mkdtemp(path.join(os.tmpdir(),'ppt-render-invalid-'));
  const plan=structuredClone(fixture);plan.slides[1].blocks[0].series[0].values=[1];
  const planPath=path.join(dir,'plan.json');await fs.writeFile(planPath,JSON.stringify(plan));
  await assert.rejects(runRenderer({plan:planPath,output:path.join(dir,'out'),stage:'sample'}),/categories|维度/);
  await assert.rejects(fs.stat(path.join(dir,'out/deck.pptx')));
});

test('sample command renders exactly the selected pages with native editable evidence',async()=>{
  const dir=await fs.mkdtemp(path.join(os.tmpdir(),'ppt-render-sample-'));
  const planPath=path.join(dir,'plan.json');await fs.writeFile(planPath,JSON.stringify(fixture));
  const output=path.join(dir,'sample');
  await runRenderer({plan:planPath,output,stage:'sample'});
  const report=JSON.parse(await fs.readFile(path.join(output,'render-report.json'),'utf8'));
  assert.deepEqual(report.slide_ids,['context','data','route']);assert.equal(report.slide_count,3);
  assert.deepEqual(report.slide_size,{width:960,height:600});
  assert.equal(report.native.charts,1);assert.equal(report.native.tables,1);
  assert.equal(report.native.embedded_workbooks,1);
  const pptxBytes=await fs.readFile(path.join(output,'deck.pptx'));
  assert.ok(pptxBytes.includes(Buffer.from('ppt/embeddings/')),'chart must include an editable workbook snapshot');
  assert.ok(report.native.textboxes>=8);assert.equal(report.checks.package_integrity,'passed');
  assert.equal(report.checks.previews,'passed');assert.match(report.plan_sha256,/^[a-f0-9]{64}$/);
  assert.ok(path.relative(dir,report.validation_receipt)&&!path.relative(dir,report.validation_receipt).startsWith('..'));
  assert.ok(path.relative(output,report.validation_receipt).startsWith('..'),'private receipt must be outside final output');
  await fs.access(report.validation_receipt);
  for(const preview of report.previews){const bytes=await fs.readFile(path.join(output,preview));assert.equal(bytes.subarray(1,4).toString(),'PNG');assert.ok(bytes.length>1000);}
});

test('mapped source slides retain selected native chrome and replace source content',async()=>{
  const dir=await fs.mkdtemp(path.join(os.tmpdir(),'ppt-render-template-'));
  const templatePlan=structuredClone(fixture);templatePlan.slides=templatePlan.slides.slice(0,3);
  templatePlan.slides[0].title='旧稿题目应被替换';
  templatePlan.slides[0].blocks=[{type:'text',text:'旧稿科研结果不进入新项目'}];
  const sourcePath=path.join(dir,'source.json');await fs.writeFile(sourcePath,JSON.stringify(templatePlan));
  await runRenderer({plan:sourcePath,output:path.join(dir,'reference'),stage:'sample'});
  const target=structuredClone(fixture);target.template=path.join(dir,'reference/deck.pptx');
  for(const page of target.slides){page.template_slide=1;page.template_preserve_names=['title-rule'];page.template_title_name='page-title';}
  const targetPath=path.join(dir,'target.json');await fs.writeFile(targetPath,JSON.stringify(target));
  const result=await runRenderer({plan:targetPath,output:path.join(dir,'target'),stage:'sample'});
  assert.equal(result.template.mode,'mapped_source_slides');
  assert.equal(result.template.source_slide_objects_preserved,true);
  assert.equal(result.template.mappings.length,3);
  assert.deepEqual(result.slide_size,{width:960,height:600});
  for(const slide of result.content_check){assert.ok(!slide.text.includes('旧稿科研结果'));assert.ok(!slide.text.includes('旧稿题目'));}
});

test('full rendering keeps input images as pictures with editable captions',async()=>{
  const dir=await fs.mkdtemp(path.join(os.tmpdir(),'ppt-render-image-'));
  const plan=structuredClone(fixture);plan.style='deep_mechanism';
  plan.slides[3].layout='title-content';
  plan.slides[3].blocks=[{type:'image',path:path.join(root,'examples/demo/materials/example-figure.png'),caption:'合成图片，仅用于技术验证',source_id:'reference-image'}];
  const input=path.join(dir,'plan.json');await fs.writeFile(input,JSON.stringify(plan));
  const report=await runRenderer({plan:input,output:path.join(dir,'full'),stage:'full'});
  assert.equal(report.slide_count,4);assert.equal(report.native.images,1);
  assert.deepEqual(report.slide_size,{width:960,height:540});
  assert.ok(report.content_check.some(s=>s.text.includes('合成图片，仅用于技术验证')));
  const expectedImageHash=createHash('sha256').update(await fs.readFile(plan.slides[3].blocks[0].path)).digest('hex');
  assert.ok(report.media_entries.some(entry=>entry.bytes>0&&entry.sha256===expectedImageHash),'actual source image bytes must be embedded, not an empty picture placeholder');
});
