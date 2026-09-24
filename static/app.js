'use strict';
const $ = (selector, root = document) => root.querySelector(selector);
const main = $('#main');
let data, routeSequence = 0, selectedMode = 'learn', selectedTestUnit = '', previewSequence = 0, bankFilter = 'all', catalogCache;
let saveTimer, saveChain = Promise.resolve();
const pending = new Map();
const typeNames = {single_choice: '选择题', short_answer: '简答题', code_fill: '代码题'};
const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const e = escapeHtml;
const unitById = id => [...data.pack.units,...data.archive.units,...(data.reference_units||[])].find(u => u.id === id);
const questionCache = new Map();
const questionById = id => questionCache.get(id);
const unitQuestions = id => [...questionCache.values()].filter(q => q.unit_id === id);
const originNames={original:'原创练习',adapted:'改编练习',licensed:'授权收录',past_exam:'历年试题',recalled:'回忆题'};
async function cacheUnit(uid){let page=1;while(true){const result=await api('/api/questions?'+new URLSearchParams({unit_id:uid,page,page_size:100}));result.items.forEach(q=>questionCache.set(q.id,q));if(page*100>=result.total)break;page++;}}
const dateText = stamp => new Date(stamp).toLocaleString('zh-CN', {month:'numeric',day:'numeric',hour:'2-digit',minute:'2-digit',timeZone:'Asia/Shanghai'});

async function api(path, payload) {
  let response;
  try {
    response = await fetch(path, payload === undefined ? {cache:'no-store'} : {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
  } catch (_) { throw new Error('暂时无法连接本地服务。输入已暂存，请启动服务后重试。'); }
  const result = await response.json();
  if (!response.ok) throw new Error(typeof result.detail === 'string' ? result.detail : '操作未成功，请检查输入后重试。');
  return result;
}

function toast(message, error = false) {
  const node = $('#toast'); node.textContent = message; node.className = 'toast' + (error ? ' error' : ''); node.hidden = false;
  clearTimeout(node.timer); node.timer = setTimeout(() => {node.hidden = true;}, error ? 6500 : 3200);
}

function saveStatus(text, error = false) { const node = $('#save-state'); node.textContent = text; node.dataset.short=error?'待重试':text.includes('正在')?'保存中':'已保存'; node.classList.toggle('error',error); }
function cachePut(key, value) { try {localStorage.setItem('zhixu:'+key, JSON.stringify(value));} catch (_) {} }
function cacheGet(key) { try {return JSON.parse(localStorage.getItem('zhixu:'+key));} catch (_) {return null;} }
function cacheRemove(key) {try {localStorage.removeItem('zhixu:'+key);} catch (_) {}}

function scheduleSave(key, endpoint, payload) {
  const item = {endpoint,payload:structuredClone(payload)};
  pending.set(key,item); cachePut(key,item.payload); saveStatus('输入已暂存 · 正在保存');
  clearTimeout(saveTimer); saveTimer = setTimeout(() => flush().catch(() => {}), 450);
}

function flush() {
  clearTimeout(saveTimer);
  saveChain = saveChain.catch(() => {}).then(async () => {
    while (pending.size) {
      const [key,item] = pending.entries().next().value;
      try {await api(item.endpoint,item.payload);} catch (err) {saveStatus('尚未保存 · 点击重试',true); throw err;}
      if (pending.get(key) === item) {pending.delete(key);cacheRemove(key);}
    }
    saveStatus('本机记录 · 已保存');
  });
  return saveChain;
}

function action(node, work) {
  node.addEventListener('click', async event => {
    event.preventDefault(); if (node.disabled) return;
    node.disabled = true;
    try {await work();} catch (err) {toast(err.message,true);} finally {node.disabled = false;}
  });
}

function nextTask() {return data.state.session?.tasks.find(t => !t.done);}
function taskLocation(task) {return task.kind === 'lesson' ? `learn/${task.unit_id}/${task.section}` : `practice/${task.question_id}`;}
function taskTitle(task) {if(task.title)return task.title;return task.kind === 'lesson' ? data.sections[task.unit_id][task.section].title : questionById(task.question_id).title;}
function navigate(target) {if (window.location.hash.slice(1) === target) render(); else window.location.hash = target;}
function completion(uid) {return data.state.units[uid]?.read_sections?.length || 0;}
function heading(title, subtitle, side = '') {return `<div class="page-heading"><div><div class="eyebrow">软件设计师 / 知识与练习</div><h1>${title}</h1>${subtitle ? `<p>${subtitle}</p>` : ''}</div>${side}</div>`;}
const icon = name => `<svg class="inline-icon" viewBox="0 0 24 24" aria-hidden="true">${({learn:'<path d="M5 5.5c2.8-.8 5-.2 7 1.4v12c-2-1.6-4.2-2.2-7-1.4zm14 0c-2.8-.8-5-.2-7 1.4v12c2-1.6 4.2-2.2 7-1.4z"/>',mistakes:'<path d="M12 3.5a8.5 8.5 0 1 0 8.5 8.5M12 7v6m0 3v.5M16.5 3.5h4v4"/>',test:'<path d="M7 4.5h10v15H7zM9.5 9l1.2 1.2L13 7.8M9.5 14l1.2 1.2L13 13m2-4h1m-1 5h1"/>',check:'<path d="m5 12 4 4 10-9"/>',arrow:'<path d="M5 12h14m-5-5 5 5-5 5"/>'})[name]}</svg>`;

function unitsGrid() {
  return `<div class="unit-grid">${data.pack.units.slice(0,3).map((u,i) => {
    const answered = Object.keys(data.summary.latest).filter(id=>questionById(id)?.unit_id===u.id).length;
    const read = completion(u.id);
    return `<article class="card unit-card"><div class="unit-card-top"><span class="unit-index">0${i+1}</span><span class="pill ${data.summary.unit_checked[u.id] ? '' : 'gray'}">${data.summary.unit_checked[u.id] ? '检查已通过' : u.tag}</span></div><h3><a href="#learn/${u.id}/0">${e(u.title)}</a></h3><p>${e(u.subtitle)}</p><div class="progress" aria-label="已读 ${read} 个小节"><span style="width:${read/data.sections[u.id].length*100}%"></span></div><div class="unit-card-bottom"><span>已读 ${read}/${data.sections[u.id].length} · 已练 ${answered}/${data.counts.by_unit[u.id]||0}</span><a href="#learn/${u.id}/0">进入单元 ↗</a></div></article>`;
  }).join('')}</div>`;
}

const modeNames = {learn:'学新知识', mistakes:'错题再练', test:'单元自测'};

function sessionRecap() {
  const session=data.state.session;
  if(!session?.completed_at||!session.tasks.length)return '';
  const answers=new Map();
  const qids=new Set(session.tasks.filter(t=>t.kind==='question').map(t=>t.question_id));
  data.state.attempts.filter(a=>a.session_id===session.id&&qids.has(a.question_id)).forEach(a=>answers.set(a.question_id,a));
  const weak=[...answers.values()].filter(a=>a.result==='incorrect'||a.uncertain);
  return `<section class="card session-recap"><span class="pill">这一组已完成</span><h3>${modeNames[session.mode||'learn']} · 本次回顾</h3><p>完成 ${session.tasks.length} 项任务 · ${answers.size} 道题 · ${weak.length} 道待巩固。主观题按自评记录，不折算考试分数。</p>${weak.length?weak.map(a=>{const q=questionById(a.question_id);return `<div class="recap-row"><div>${resultBadge(a)} <a href="#practice/${q.id}">${e(q.title)}</a>${a.uncertain?' <small>已标记不确定</small>':''}</div><a href="#learn/${q.unit_id}/${q.section_index||0}">回看相关讲解 ↗</a></div>`;}).join(''):'<p class="muted">本组暂无待巩固题，可以继续学习，也可以在这里结束。</p>'}</section>`;
}

function renderToday() {
  const session=data.state.session, task=nextTask();
  main.innerHTML=heading('今天，从一个明确目标开始。','选择目的，确认这一组内容，再开始学习。')
    +`${task?`<section class="continue-strip card"><div><span class="continue-kicker">上次停在这里</span><strong>${e(modeNames[session.mode||'learn'])} · ${e(taskTitle(task))}</strong></div><button class="button secondary" id="resume-active">继续上次任务 ${icon('arrow')}</button></section>`:''}`
    +`<section class="study-planner" aria-labelledby="planner-title"><div class="planner-head"><span class="eyebrow">本次学习安排</span><h2 id="planner-title">先选目的，再看任务</h2><ol class="planner-steps" aria-label="开始学习的步骤"><li class="active"><span>1</span>选择目的</li><li><span>2</span>预览任务</li><li><span>3</span>开始学习</li></ol></div><div class="mode-options" role="group" aria-label="学习目的">${Object.entries(modeNames).map(([mode,label])=>`<button data-mode="${mode}" aria-pressed="${selectedMode===mode}" class="${selectedMode===mode?'selected':''}">${icon(mode)}<span>${label}${mode==='mistakes'?'<small id="mistake-count"></small>':''}</span></button>`).join('')}</div><div class="planner-body"><div class="planner-choice"><div id="test-unit-field" hidden><label for="test-unit">自测单元</label><select id="test-unit"></select></div><section id="mode-focus" aria-live="polite"><span class="pill">准备学习</span><h3>选择一个学习目的</h3><p>右侧会显示这一组的具体任务。</p></section></div><section class="task-preview-panel"><div class="preview-heading"><span>任务预览</span><small>预览不会开始任务</small></div><div id="task-preview" aria-live="polite">正在准备任务…</div></section></div><div class="planner-action" id="planner-action"><button class="button primary" type="button" disabled>正在准备任务…</button></div></section>`
    +sessionRecap()+`<div class="section-heading"><h2>当前考试专题</h2><a href="#practice">${data.counts.questions} 道练习 ↗</a></div>${unitsGrid()}`
    +`<div class="stats-strip"><div class="stat"><strong>${data.summary.answered}<small> / ${data.counts.questions}</small></strong><span>已练习题目</span></div><div class="stat"><strong>${data.summary.first_total?data.summary.first_correct+'/'+data.summary.first_total:'—'}</strong><span>首次独立选择题答对</span></div><div class="stat"><strong>${data.summary.mistakes.length}</strong><span>待巩固题目</span></div></div>`;
  document.querySelectorAll('[data-mode]').forEach(button=>button.addEventListener('click',()=>{
    selectedMode=button.dataset.mode;updateModePreview().catch(err=>toast(err.message,true));
  }));
  $('#test-unit').addEventListener('change',event=>{selectedTestUnit=event.target.value;updateModePreview().catch(err=>toast(err.message,true));});
  if($('#resume-active')) action($('#resume-active'),async()=>{await flush();navigate(taskLocation(task));});
  return updateModePreview();
}

async function updateModePreview() {
  const sequence=++previewSequence, route=routeSequence;
  document.querySelectorAll('[data-mode]').forEach(button=>{const chosen=button.dataset.mode===selectedMode;button.classList.toggle('selected',chosen);button.setAttribute('aria-pressed',chosen);});
  $('#test-unit-field').hidden=selectedMode!=='test';
  $('#task-preview').textContent='正在准备任务…';
  $('#planner-action').innerHTML='<button class="button primary" type="button" disabled>正在准备任务…</button>';
  const previous=$('#start-session');if(previous)previous.disabled=true;
  const params=new URLSearchParams({mode:selectedMode});if(selectedMode==='test'&&selectedTestUnit)params.set('unit_id',selectedTestUnit);
  let plan;
  try {plan=await api('/api/session/preview?'+params);}
  catch(err){if(sequence===previewSequence&&route===routeSequence){$('#task-preview').textContent='任务暂未加载，请重新选择模式重试。';}throw err;}
  if(sequence!==previewSequence||route!==routeSequence)return;
  $('#mistake-count').textContent=' · '+plan.mistake_count;
  if(selectedMode==='test'){
    selectedTestUnit=plan.unit_id||'';
    $('#test-unit').innerHTML=plan.test_units.length?plan.test_units.map(u=>`<option value="${e(u.id)}" ${u.id===selectedTestUnit?'selected':''}>${e(u.title)}</option>`).join(''):'<option value="">暂无已学单元</option>';
    $('#test-unit').disabled=!plan.test_units.length;
  }
  const remaining=plan.tasks.filter(t=>!t.done), questions=remaining.filter(t=>t.kind==='question').length;
  const descriptions={learn:'一小节讲解，配上对应练习。理解之后，再检查自己。',mistakes:'重新作答最新答错或不确定的题目，每组最多五题。原有作答记录保留。',test:'每组最多五题，尽量覆盖不同知识点。逐题反馈，完成后查看薄弱点与复习入口。'};
  $('#mode-focus').innerHTML=`<span class="pill">${plan.resuming?'该模式有未完成进度':'已选择'}</span><h3>${icon(selectedMode)}${modeNames[selectedMode]}</h3><p>${e(plan.empty_reason||descriptions[selectedMode])}</p>${plan.tasks.length?`<div class="plan-estimate">剩余 ${remaining.length} 项 · ${questions} 道题 · 预计 ${plan.minutes} 分钟</div>`:''}`;
  const visible=remaining.slice(0,3), hidden=remaining.slice(3);
  const taskRows=(tasks,offset=0)=>tasks.map((t,i)=>`<div class="task-row"><span class="step ${t.done?'done':''}">${t.done?icon('check'):offset+i+1}</span><div>${e(t.title)}<small>${t.done?'已完成':'约 '+t.minutes+' 分钟 · '+(t.kind==='lesson'?'阅读':'练习')}</small></div></div>`).join('');
  $('#task-preview').innerHTML=plan.tasks.length?`${plan.tasks.some(t=>t.done)?`<p class="completed-summary">${plan.tasks.filter(t=>t.done).length} 项已完成，本次从剩余任务继续。</p>`:''}${taskRows(visible)}${hidden.length?`<details class="more-tasks"><summary>再看其余 ${hidden.length} 项</summary>${taskRows(hidden,visible.length)}</details>`:''}`:`<p class="mode-empty">${e(plan.empty_reason)}</p>`;
  $('#planner-action').innerHTML=plan.tasks.length?`<button class="button primary" id="start-session">${plan.resuming?'继续这一组':'开始这一组'} ${icon('arrow')}</button><a class="button ghost" href="#learn">先去知识库看看</a>`:`<a class="button secondary" href="#learn">去知识库学习</a><a class="button ghost" href="#practice">自由练习</a>`;
  if($('#start-session'))action($('#start-session'),async()=>{
    await flush();const session=await api('/api/session',{mode:plan.mode,unit_id:plan.unit_id});
    navigate(taskLocation(session.tasks.find(t=>!t.done)));
  });
}

function pageControls(result) {
  return `<div class="pagination"><button class="button secondary" data-page="${result.page-1}" ${result.page===1?'disabled':''}>上一页</button><span>第 ${result.page} 页 · 共 ${result.total} 条</span><button class="button secondary" data-page="${result.page+1}" ${result.page*result.page_size>=result.total?'disabled':''}>下一页</button></div>`;
}
function connectPages(view, params){document.querySelectorAll('[data-page]').forEach(b=>action(b,async()=>{params.set('page',b.dataset.page);navigate(view+'?'+params);}));}
function selectField(name,label,options,value=''){return `<label>${label}<select name="${name}"><option value="">全部</option>${options.map(([id,title])=>`<option value="${e(id)}" ${String(value)===String(id)?'selected':''}>${e(title)}</option>`).join('')}</select></label>`;}
function connectSearch(view){$('#filter-form').addEventListener('submit',event=>{event.preventDefault();const params=new URLSearchParams(new FormData(event.target));for(const [key,value] of [...params])if(!value)params.delete(key);navigate(view+'?'+params);});}
async function renderLibrary(sequence) {
  const params=new URLSearchParams(location.hash.split('?')[1]||'');
  const result=await api('/api/topics?'+params);if(sequence!==routeSequence)return;
  main.innerHTML=heading('把知识连成体系。','八个板块，按考点阅读、推导和练习。C++ 主线 · C 算法训练。')
    +`<form id="filter-form" class="card filter-panel"><label class="search-field">搜索知识<input name="q" placeholder="例如：死锁、虚函数、事务" value="${e(params.get('q')||'')}"></label>${selectField('module','知识板块',data.modules.map(m=>[m.id,m.title]),params.get('module'))}<button class="button primary">搜索</button></form>`
    +`<div class="module-strip">${data.modules.map(m=>`<a href="#learn?module=${m.id}" class="module-chip ${params.get('module')===m.id?'selected':''}"><small>${m.id}</small>${e(m.title)}</a>`).join('')}</div>`
    +`<section class="card question-list">${result.items.map(t=>`<a class="question-list-row" href="#learn/${t.id}/0"><span class="topic-index">${e(t.id)}</span><div><small>${e(data.modules.find(m=>m.id===t.module_id)?.units.find(u=>u.id===t.unit_id)?.title||t.module_id)}</small><h3>${e(t.title)}</h3><p>${e(t.objectives.join('；'))}</p><small>${t.question_ids.length} 道关联练习 · 约 ${t.minutes} 分钟</small></div><span class="pill gray">${t.review_status==='reviewed'?'已审校':'待核验'}</span></a>`).join('')||'<div class="empty">没有匹配的考点，试试名称或英文别名。</div>'}</section>`
    +pageControls(result)+`<details class="card tools-card"><summary>原有专题与基础归档</summary>${[...data.pack.units.filter(u=>u.id.startsWith('SE-')),...data.archive.units].map(u=>`<p><a href="#learn/${u.id}/0">${e(u.title)}</a> · <a href="#practice?unit_id=${u.id}">练习</a></p>`).join('')}</details><p class="muted">覆盖的是当前登记考点；完整官方大纲细目核验状态：${e(data.report.syllabus_status==='publisher_verified_full_outline_pending'?'待补齐官方正文':'见覆盖记录')}。</p>`;
  connectSearch('learn');connectPages('learn',params);
}

function sources(uid) {
  const u = unitById(uid);
  return `<details class="sources"><summary>资料来源与内容说明</summary>${[...data.pack.sources,...data.archive.sources].filter(s=>u.source_ids.includes(s.id)).map(s=>`<a href="${e(s.url)}" target="_blank" rel="noopener noreferrer">${e(s.title)} ↗</a>`).join('')}<p>题目来源类型单独标注；第三方解析不等同于官方标准答案。技术文档和教材用于核验。难度为编辑判断。内容版本 ${e(u.version)}。</p></details>`;
}

function binaryDiagramMarkup() {
  return `<section class="binary-demo" tabindex="-1" aria-labelledby="binary-demo-title"><div class="demo-heading"><div><span class="eyebrow">交互图解 · 页面内练习</span><h3 id="binary-demo-title">逐步跟踪闭区间二分查找</h3><p>选择目标后手动前进。步骤不会写入学习记录。</p></div><div class="target-switch" role="group" aria-label="选择查找目标"><button type="button" data-binary-target="47" aria-pressed="true">查找 47</button><button type="button" data-binary-target="35" aria-pressed="false">查找 35</button></div></div><div class="binary-stage"><div class="binary-array" id="binary-array" aria-label="有序数组"></div><div class="binary-state" id="binary-state" role="status" aria-live="polite"></div></div><div class="binary-controls"><button class="button secondary" type="button" id="binary-prev">← 上一步</button><span id="binary-counter"></span><button class="button primary" type="button" id="binary-next">下一步 →</button><button class="button ghost" type="button" id="binary-reset">重置</button></div></section>`;
}

function connectBinaryDiagram() {
  let target=47, stepIndex=0, trace=BinarySearchDiagram.buildTrace(target);
  const phaseNames={initial:'初始区间',compare:'比较中间元素',update:'更新边界',terminal:'查找终止'};
  function paint(){
    const step=trace[stepIndex];
    $('#binary-array').innerHTML=BinarySearchDiagram.values.map((value,index)=>{const labels=[];if(index===step.low)labels.push('low');if(index===step.mid)labels.push('mid');if(index===step.high)labels.push('high');return `<div class="array-cell ${index<step.low||index>step.high?'excluded':''} ${index===step.mid?'mid':''}"><span>${index}</span><strong>${value}</strong><small>${labels.join('<br>')||'&nbsp;'}</small></div>`;}).join('');
    const mid=step.mid===null?'—':`${step.mid}（值 ${BinarySearchDiagram.values[step.mid]}）`;
    const result=step.result===null?'尚未返回':`返回 ${step.result}`;
    $('#binary-state').innerHTML=`<span class="phase">${phaseNames[step.phase]}</span><dl><div><dt>low</dt><dd>${step.low}</dd></div><div><dt>mid</dt><dd>${mid}</dd></div><div><dt>high</dt><dd>${step.high}</dd></div><div><dt>结果</dt><dd>${result}</dd></div></dl><p>${e(step.message)}</p>`;
    $('#binary-counter').textContent=`步骤 ${stepIndex+1} / ${trace.length}`;
    $('#binary-prev').disabled=stepIndex===0;$('#binary-next').disabled=stepIndex===trace.length-1;
  }
  document.querySelectorAll('[data-binary-target]').forEach(button=>button.addEventListener('click',()=>{target=Number(button.dataset.binaryTarget);trace=BinarySearchDiagram.buildTrace(target);stepIndex=0;document.querySelectorAll('[data-binary-target]').forEach(item=>item.setAttribute('aria-pressed',String(item===button)));paint();}));
  $('#binary-prev').addEventListener('click',()=>{if(stepIndex>0)stepIndex--;paint();});
  $('#binary-next').addEventListener('click',()=>{if(stepIndex<trace.length-1)stepIndex++;paint();});
  $('#binary-reset').addEventListener('click',()=>{stepIndex=0;paint();});
  paint();
}

function enhanceLessonSemantics() {
  document.querySelectorAll('.reading-prose p').forEach(paragraph=>{
    const label=paragraph.querySelector('strong:first-child')?.textContent.replace(/[：:]/g,'').trim();
    const kind=label==='目标'?'objective':label?.includes('易错')?'warning':label==='自查'?'check':null;
    if(kind)paragraph.classList.add('semantic-note',`semantic-${kind}`);
  });
}

async function renderLesson(uid, index, sequence) {
  const response=await api('/api/lesson/'+uid);await cacheUnit(uid);if(sequence!==routeSequence)return;data.sections[uid]=response.sections;
  const u = unitById(uid); if (!u) throw new Error('单元不存在');
  const sections = data.sections[uid]; index = Number(index || 0);
  if (!sections[index]) index=0;
  const s=sections[index], progress=data.state.units[uid]?.read_sections||[];
  const missing = u.prerequisite_ids.filter(id=>!data.summary.unit_checked[id]&&!data.state.units[id]?.override);
  const supplementary=uid==='B03-T09'?`<aside class="supplement-link"><div>${icon('learn')}<div><strong>想看数组查找的过程？</strong><p>这里讲的是分治与二分答案；补充图解演示的是有序数组二分查找，两者不是同一段正文。</p></div></div><a class="button secondary" href="#learn/SE-02/2">数组二分补充图解 ${icon('arrow')}</a></aside>`:'';
  const diagram=uid==='SE-02'&&index===2?binaryDiagramMarkup():'';
  main.innerHTML = heading(e(u.title),e(u.subtitle),`<a class="button secondary" href="#practice?unit_id=${uid}">直接练习 ↗</a>`)
    + `${missing.length ? `<div class="notice">这课会用到「${missing.map(id=>e(unitById(id).title)).join('、')}」的知识。你仍可自由阅读。<div class="actions"><a class="button ghost" href="#learn/${missing[0]}/0">先回顾上一课</a><button class="button secondary" id="override">我已了解先修内容，跳过检查</button></div></div>`:''}`
    + `<div class="learn-layout"><div><article class="card reading-card"><header class="reading-top"><div><span class="pill">正在学习 · 小节 ${index+1} / ${sections.length}</span>${u.title!==s.title?`<h2 class="lesson-title">${e(s.title)}</h2>`:''}</div><span>约 ${s.minutes} 分钟 ${progress.includes(index)?'· 已读':''}</span></header>${diagram?'<button class="jump-to-demo" id="jump-binary" type="button">查看交互图解 ↓</button>':''}${supplementary}<div class="prose reading-prose">${s.html}</div>${diagram}<div class="reading-nav"><a class="button ghost" href="#learn/${uid}/${Math.max(0,index-1)}">${index?'← 上一小节':'回到本课开头'}</a><button class="button primary" id="finish-section">${nextTask()?'读完了，继续任务':index<sections.length-1?'读完了，下一小节':'读完了，做几道题'} →</button></div></article>
    <section class="card note-card"><label for="lesson-note">一句话收获 <span class="muted">/ 想记就记</span></label><textarea id="lesson-note" rows="3" maxlength="15000" placeholder="用自己的话记下一点理解，或暂时没想明白的问题。"></textarea><span class="saved-label" id="note-status">输入后自动保存</span></section>${sources(uid)}</div>
    <aside class="lesson-aside"><nav class="card toc" aria-label="本课目录"><div class="eyebrow">本课目录</div>${sections.map((sec,i)=>`<a href="#learn/${uid}/${i}" class="${i===index?'active':''}" ${i===index?'aria-current="location"':''}><span>${progress.includes(i)?'✓':String(i+1).padStart(2,'0')}</span>${e(sec.title)}</a>`).join('')}</nav><div class="objectives"><h3>学完，你可以</h3><ul>${u.objectives.map(o=>`<li>${e(o)}</li>`).join('')}</ul><button class="button ghost" id="lesson-feedback">这段内容有疑问？</button></div></aside></div>`;
  enhanceLessonSemantics();
  if(diagram){connectBinaryDiagram();$('#jump-binary').addEventListener('click',()=>{const demo=$('.binary-demo');demo.scrollIntoView({block:'start',behavior:'smooth'});demo.focus({preventScroll:true});});}
  const key='note:'+uid,cached=cacheGet(key),note=$('#lesson-note');
  note.value=cached?.text ?? data.state.notes[uid] ?? '';
  if(cached) scheduleSave(key,'/api/note/'+uid,cached);
  note.addEventListener('input',()=>scheduleSave(key,'/api/note/'+uid,{text:note.value}));
  action($('#finish-section'),async()=>{
    const inSession = !data.state.session?.completed_at && data.state.session?.tasks.some(t=>t.kind==='lesson'&&t.unit_id===uid&&t.section===index);
    await flush();await api('/api/read',{unit_id:uid,section:index});
    await load();
    const task=nextTask();
    if(inSession&&task) navigate(taskLocation(task));
    else if(inSession&&data.state.session?.completed_at) {toast('这一组学习完成了。');navigate('today');}
    else navigate(index<sections.length-1?`learn/${uid}/${index+1}`:`practice/${unitQuestions(uid)[0].id}`);
  });
  if($('#override')) action($('#override'),async()=>{for(const prior of missing) await api('/api/override/'+prior,{});await render();});
  $('#lesson-feedback').addEventListener('click',()=>openFeedback(`${u.title} / ${s.title}：\n`));
}

function resultLabel(a) {return a.result==='pending'?'待自评':a.result==='correct'?(a.assessment_method==='self-rated'?'自评通过':'回答正确'):(a.assessment_method==='self-rated'?'自评待巩固':'回答错误');}
function resultBadge(a) {const symbol=a.result==='correct'?'✔':a.result==='incorrect'?'❌':'◷';return `<span class="result-badge ${a.result}"><span class="result-icon" aria-hidden="true">${symbol}</span><span>${resultLabel(a)}</span></span>`;}
function revealResult() {const target=$('#reference .result-label');if(target){target.scrollIntoView({block:'center',behavior:'instant'});target.focus({preventScroll:true});}}
async function renderBank(sequence) {
  const params=new URLSearchParams(location.hash.split('?')[1]||'');
  catalogCache=catalogCache||await api('/api/catalog');
  if(params.has('unit')){params.set('unit_id',params.get('unit'));params.delete('unit');}
  if(catalogCache.topics.some(t=>t.id===params.get('unit_id'))){params.set('topic',params.get('unit_id'));params.delete('unit_id');}
  if(bankFilter==='mistakes'){params.set('mistakes','true');bankFilter='all';}
  const result=await api('/api/questions?'+params);if(sequence!==routeSequence)return;
  result.items.forEach(q=>questionCache.set(q.id,q));
  main.innerHTML=heading('用练习，检查理解。','先独立作答，再看推导。案例和代码题按要点自评。',`<a class="button secondary" href="#practice?mistakes=true">错题与不确定</a>`)
    +`<form id="filter-form" class="card filter-panel"><label class="search-field">搜索题目<input name="q" value="${e(params.get('q')||'')}" placeholder="题目标题或题干关键词"></label>${selectField('module','板块',data.modules.map(m=>[m.id,m.title]),params.get('module'))}${selectField('type','题型',Object.entries(typeNames),params.get('type'))}${selectField('difficulty','难度',[['basic','基础辨析'],['applied','考点应用'],['comprehensive','综合推导']],params.get('difficulty'))}${selectField('origin','来源',Object.entries(originNames),params.get('origin'))}${selectField('topic','考点',catalogCache.topics.filter(t=>!params.get('module')||t.module_id===params.get('module')).map(t=>[t.id,t.title]),params.get('topic'))}${params.get('unit_id')?`<input type="hidden" name="unit_id" value="${e(params.get('unit_id'))}">`:''}${params.get('mistakes')?'<input type="hidden" name="mistakes" value="true">':''}<button class="button primary">筛选</button><a class="button ghost" href="#practice">重置</a></form>`
    +`<section class="card question-list">${result.items.map(q=>`<a class="question-list-row" href="#practice/${q.id}"><span class="topic-index">${e(q.id)}</span><div><h3>${e(q.title)}</h3><p>${e(unitById(q.unit_id)?.title||q.module_id||'历年试题')} · ${typeNames[q.type]} · ${originNames[q.origin_kind]||q.origin_kind} · ${q.minutes} 分钟</p></div>${data.summary.latest[q.id]?resultBadge(data.summary.latest[q.id]):'<span class="pill gray">未练习 ↗</span>'}</a>`).join('')||'<div class="empty">没有匹配的题目。</div>'}</section>`+pageControls(result);
  connectSearch('practice');connectPages('practice',params);
}

async function renderPapers(sequence,pid) {
  const labels={complete:'完整收录',partial:'部分正文',index_only:'仅来源索引',missing:'材料缺失'};
  if(pid){
    const paper=await api('/api/paper/'+pid);if(sequence!==routeSequence)return;
    main.innerHTML=heading(e(paper.title),`${paper.year} · ${paper.session==='H1'?'上半年':'下半年'} · ${paper.subject==='comprehensive'?'综合知识':'应用技术'} · ${e(paper.batch==='unknown'?'批次未核实':paper.batch)}`, '<a class="button secondary" href="#exams">返回真题库</a>')
      +`<section class="card tools-card"><span class="pill gray">${labels[paper.completeness]}</span> <span class="pill gray">${paper.origin_kind==='recalled'?'回忆或第三方整理':'来源见记录'}</span><p>${e(Array.isArray(paper.notes)?paper.notes.join('；'):paper.notes)}</p><p>答案状态：${paper.answer_status==='verified'?'已核验':'待核验'} · 收录正文 ${paper.questions.length} 题</p>${paper.sources.map(s=>`<p><a href="${e(s.url)}" target="_blank" rel="noopener noreferrer">${e(s.title)} ↗</a><small> ${e(s.locator)}</small></p>`).join('')}</section>`
      +`<section class="card question-list">${paper.questions.map((q,i)=>`<a class="question-list-row" href="#practice/${q.id}"><span>${e(q.original_number||i+1)}</span><div><h3>${e(q.title)}</h3><p>${q.answer_status==='verified'?'答案已核验':'仅查阅 · 答案待核验'}</p></div></a>`).join('')||'<div class="empty">当前记录仅包含试卷来源定位，尚未收录可练习正文。</div>'}</section>`;
    return;
  }
  const params=new URLSearchParams(location.hash.split('?')[1]||'');const result=await api('/api/papers?'+params);if(sequence!==routeSequence)return;
  main.innerHTML=heading('历年真题，保留来处。','2005 年至今 · 区分正文收录、来源索引与回忆版。')
    +`<div class="stats-strip"><div class="stat"><strong>${data.report.papers}</strong><span>试卷目录记录</span></div><div class="stat"><strong>${data.report.exam_questions}</strong><span>已收录正文题目</span></div><div class="stat"><strong>${data.report.complete_papers}</strong><span>完整收录试卷</span></div></div><form id="filter-form" class="card filter-panel">${selectField('year','年份',[...new Set(result.coverage.entries.map(r=>r.year))].sort((a,b)=>b-a).map(y=>[y,y]),params.get('year'))}${selectField('session','考期',[['H1','上半年'],['H2','下半年']],params.get('session'))}${selectField('subject','科目',[['comprehensive','综合知识'],['applied','应用技术']],params.get('subject'))}<label>批次<input name="batch" value="${e(params.get('batch')||'')}" placeholder="unknown / 1"></label><button class="button primary">筛选</button></form>`
    +`<section class="card question-list">${result.items.map(p=>`<a class="question-list-row" href="#exams/${p.id}"><span class="topic-index">${p.year}<small>${p.session}</small></span><div><h3>${e(p.title)}</h3><p>${p.question_ids.length} 题正文 · ${e(p.batch==='unknown'?'批次未核实':p.batch)} · 答案${p.answer_status==='verified'?'已核验':'待核验'}</p></div><span class="pill gray">${labels[p.completeness]}</span></a>`).join('')||'<div class="empty">该条件下没有已建立的试卷记录。</div>'}</section>`+pageControls(result)
    +`<details class="card tools-card"><summary>全时段缺口与检索状态</summary><div class="coverage-table"><table><thead><tr><th>年份</th><th>考期</th><th>科目</th><th>状态</th><th>说明</th></tr></thead><tbody>${(result.coverage.entries||[]).map(r=>`<tr><td>${r.year}</td><td>${r.session}</td><td>${r.subject==='comprehensive'?'综合':'应用'}</td><td>${e(labels[r.status]||({not_held_yet:'尚未举行',unverified:'待核实'}[r.status])||r.status)}</td><td>${e(r.note)}</td></tr>`).join('')}</tbody></table></div></details>`;
  connectSearch('exams');connectPages('exams',params);
}

async function renderQuestion(qid, sequence) {
  const response=await api('/api/question/'+qid);await cacheUnit(response.question.unit_id);if(sequence!==routeSequence)return;questionCache.set(qid,response.question);
  const q=response.question,u=unitById(q.unit_id)||{id:q.unit_id,title:'历年试题'},key='draft:'+qid+(data.state.session?.mode&&data.state.session.tasks.some(t=>t.question_id===qid)?':'+data.state.session.id:'');
  if(q.answer_status&&q.answer_status!=='verified'){main.innerHTML=heading(e(q.title),'仅供查阅 · 题目或答案尚未核验')+`<article class="card reading-card"><div class="question-prompt prose">${q.prompt_html||e(q.prompt)}</div>${q.case_material?`<pre>${e(q.case_material)}</pre>`:''}${(q.subquestions||[]).map(s=>`<p>${e(s.id)}. ${e(s.prompt)}</p>`).join('')}${q.options?Object.entries(q.options).map(([k,v])=>`<p>${e(k)}. ${e(v)}</p>`).join(''):''}${q.code?`<pre>${e(q.code)}</pre>`:''}</article>`;return;}
  if(response.attempt) cacheRemove(key);
  const cached=response.attempt?null:cacheGet(key);
  const draft=cached||response.draft||{answer:{},uncertain:false,submission_key:crypto.randomUUID()};
  let attempt=response.attempt;
  const session=data.state.session;
  const inSession=!!session?.mode&&session.tasks.some(t=>t.question_id===qid);
  const practiceQuestions=inSession?session.tasks.filter(t=>t.kind==='question').map(t=>questionById(t.question_id)).filter(Boolean):unitQuestions(q.unit_id);
  const context=inSession?`${modeNames[session.mode]} · 第 ${practiceQuestions.findIndex(item=>item.id===qid)+1} / ${practiceQuestions.length} 题`:'每次作答都是一次检查，拿不准也可以如实记录。';
  const fields=q.type==='single_choice'?Object.entries(q.options).map(([id,label])=>`<label class="option"><input type="radio" name="option" value="${id}" ${draft.answer.option===id?'checked':''}><span class="option-key">${id}</span><span>${e(label)}</span></label>`).join('')
    :q.type==='short_answer'?`<div class="answer-fields"><label for="answer-text">你的回答</label><textarea id="answer-text" rows="6" maxlength="15000" placeholder="先用自己的话写出思路，不需要与参考答案一字不差。">${e(draft.answer.text||'')}</textarea></div>`
    :`<div class="answer-fields"><label for="answer-blank">空白处填写</label><input type="text" id="answer-blank" maxlength="15000" autocomplete="off" spellcheck="false" placeholder="多处填空请按编号依次填写" value="${e(draft.answer.blank||'')}"><label for="answer-explanation">结果与推导</label><textarea id="answer-explanation" rows="4" maxlength="15000" placeholder="写出结果、推导过程，以及题目要求的复杂度或边界解释。">${e(draft.answer.explanation||'')}</textarea></div>`;
  const questionDone=item=>inSession?session.tasks.some(task=>task.question_id===item.id&&task.done):!!data.summary.latest[item.id];
  main.innerHTML=heading(e(u.title),context,`<a class="button secondary" href="#learn/${u.id}/0">回看讲解</a>`)+`<div class="question-layout"><section class="card question-card"><div class="question-meta"><span>${typeNames[q.type]} · ${e(q.difficulty||'旧版基础')}</span><span>${e(q.id)}</span></div><h2>${e(q.title)}</h2>${q.exam_anchor?`<p class="exam-anchor">${e(q.exam_anchor)} · ${originNames[q.origin_kind]||'来源见记录'}${q.language?' · '+e(q.language.toUpperCase()):''}</p>`:''}<p class="muted">${e(originNames[q.origin_kind]||'来源见记录')} · ${q.answer_status==='verified'?'答案已核验':'参考解析'}</p>${q.case_material?`<section class="case-material"><h3>共享案例材料</h3><div class="prose">${q.case_html||e(q.case_material)}</div></section>`:''}${(q.assets||[]).map(a=>`<figure><img class="case-image" src="/content-assets/${e(a.path)}" alt="${e(a.alt)}"><figcaption>${e(a.alt)}</figcaption></figure>`).join('')}<div class="question-prompt prose">${q.prompt_html||e(q.prompt)}</div>${(q.subquestions||[]).map(s=>`<div class="case-subquestion"><strong>${e(s.id)}${s.points!=null?' · '+s.points+' 分':''}</strong><p>${e(s.prompt)}</p></div>`).join('')}${q.code?`<pre class="question-code"><code>${e(q.code)}</code></pre>`:''}<form id="answer-form"><fieldset style="border:0;padding:0;margin:0" ${attempt?'disabled':''}><legend class="sr-only" style="position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0,0,0,0)">填写答案</legend>${fields}<label class="uncertain"><input id="uncertain" type="checkbox" ${draft.uncertain?'checked':''}>不太确定 / 这次有猜测</label></fieldset>${!attempt?'<div class="answer-actions"><button class="button primary" type="submit" id="submit-answer">提交答案</button><button type="button" class="button ghost" id="reveal-answer">先看看解析</button></div>':''}</form><div id="reference"></div><div class="answer-actions" id="after-actions" ${attempt?'':'hidden'}><button class="button primary" id="next-question">继续 →</button><button class="button secondary" id="retry-question">重新作答</button><a class="button ghost" href="#practice">返回题目列表</a></div></section><aside><div class="card question-map"><h3>${inSession?modeNames[session.mode]:'本课练习'}</h3><div class="map-grid">${practiceQuestions.map((item,i)=>`<a href="#practice/${item.id}" class="${item.id===q.id?'active':questionDone(item)?'completed':''}">${i+1}</a>`).join('')}</div><p>选择题自动反馈。简答与代码题按要点自评。</p></div>${sources(u.id)}</aside></div>`;
  const readAnswer=()=>q.type==='single_choice'?{option:$('input[name=option]:checked')?.value||''}:q.type==='short_answer'?{text:$('#answer-text').value}:{blank:$('#answer-blank').value,explanation:$('#answer-explanation').value};
  const capture=()=>({question_id:qid,answer:readAnswer(),uncertain:$('#uncertain').checked,submission_key:draft.submission_key});
  if(!attempt){
    $('#answer-form').addEventListener('input',()=>scheduleSave(key,'/api/draft',capture()));
    if(cached) scheduleSave(key,'/api/draft',capture());
    $('#answer-form').addEventListener('submit',async event=>{
      event.preventDefault(); const button=$('#submit-answer');if(button.disabled)return;
      button.disabled=true;
      try{await flush();await api('/api/submit',capture());cacheRemove(key);await render();revealResult();}
      catch(err){toast(err.message,true);}finally{button.disabled=false;}
    });
    action($('#reveal-answer'),async()=>{await flush();const ref=await api('/api/reveal/'+qid,{});showReference(ref,null,q);toast('已记录参考答案的查看，本次不会计为独立首答。');});
  }
  if(attempt) showReference(response.reference,attempt,q);
  action($('#retry-question'),async()=>{await flush();await api('/api/retry/'+qid,{});cacheRemove(key);await render();});
  if(attempt?.result==='pending') $('#next-question').textContent='稍后自评，返回列表';
  action($('#next-question'),async()=>{
    if(attempt?.result==='pending'){navigate('practice');return;}
    await load();const task=nextTask();
    if(task) navigate(taskLocation(task));
    else if(data.state.session?.completed_at&&data.state.session.tasks.some(t=>t.question_id===qid)) navigate('today');
    else {const qs=unitQuestions(q.unit_id),index=qs.findIndex(item=>item.id===qid);navigate(index<qs.length-1?'practice/'+qs[index+1].id:'review');}
  });
}

function showReference(ref,attempt,q) {
  const result=attempt?`<div class="result-label ${attempt.result}" tabindex="-1" role="status">${resultBadge(attempt)}${attempt.assisted?' · 参考后作答':''}${attempt.uncertain?' · 已标记不确定':''}</div>`:'<div class="result-label">已查看解析 · 仍可提交你的理解</div>';
  $('#reference').innerHTML=`<div class="answer-reference">${result}<h3 style="margin-top:12px">${q.type==='single_choice'?'答案 '+e(ref.answer):'参考答案与思路'}</h3>${q.type==='single_choice'?'':`<pre>${e(ref.answer)}</pre>`}<p>${e(ref.explanation)}</p>${ref.option_explanations?`<ul class="option-analysis">${Object.entries(ref.option_explanations).map(([id,text])=>`<li>${id} · ${e(text)}</li>`).join('')}</ul>`:''}${ref.rubric?`<div id="rubric"><h3 style="margin-top:20px">对照要点，检查自己的回答</h3><p class="muted" style="font-size:13px">意思一致即可；这份自评用于学习，不是考试评分。</p>${ref.rubric.map(r=>`<div class="rubric-row"><p>${e(r.text)}</p><div class="rubric-options">${[['full','满足'],['partial','部分满足'],['missed','未满足']].map(([value,label])=>`<label><input type="radio" name="rubric-${r.id}" value="${value}" ${attempt?.ratings?.[r.id]===value?'checked':''} ${!attempt||attempt.result!=='pending'?'disabled':''}>${label}</label>`).join('')}</div></div>`).join('')}${attempt?.result==='pending'?'<button class="button primary" id="save-assessment" style="margin-top:20px">保存自评</button>':!attempt?'<p class="muted" style="margin-top:15px">提交你的回答后，即可保存自评。</p>':''}</div>`:''}</div>`;
  if($('#save-assessment')) action($('#save-assessment'),async()=>{
    const ratings={};ref.rubric.forEach(r=>{const radio=$(`input[name="rubric-${r.id}"]:checked`);if(radio)ratings[r.id]=radio.value;});
    if(Object.keys(ratings).length!==ref.rubric.length) throw new Error('请对每个要点评价后再保存。');
    await api('/api/assessment/'+attempt.id,{ratings});toast('自评已保存');await render();revealResult();
  });
}

function formatAnswer(a) {return Object.entries(a.answer).map(([key,value])=>({option:'选择',text:'回答',blank:'填空',explanation:'说明'}[key]||key)+'：'+value).join('\n');}

function renderReview() {
  const s=data.summary,attempts=[...data.state.attempts].reverse();
  const completed=data.pack.units.filter(u=>completion(u.id)===data.sections[u.id].length).length;
  main.innerHTML=heading('看看走过的这一小段。','新版统计仅计当前考试专题；旧版作答与笔记仍在下方历史中保留。',`<button class="button secondary" id="review-feedback">留下反馈 ↗</button>`)
    + `<div class="review-stats"><div class="card metric"><p>已读完的单元</p><strong>${completed}<small> / ${data.counts.units}</small></strong><small>读完与通过检查分别记录</small></div><div class="card metric"><p>首次独立选择题答对</p><strong>${s.first_total?s.first_correct+' / '+s.first_total:'—'}</strong><small>参考后作答、主观题不混入</small></div><div class="card metric"><p>待巩固题目</p><strong>${s.mistakes.length}</strong><small>最新做错或标记不确定</small></div></div>
    <div class="actions"><button class="button primary" id="review-mistakes">错题与不确定再练 →</button>${s.pending.length?`<span class="pill warm">${s.pending.length} 次作答待自评</span>`:''}</div>
    <div class="section-heading"><h2>作答记录</h2><span class="muted" style="font-size:13px">共 ${attempts.length} 次</span></div><section class="card">${attempts.length?attempts.map(a=>`<div class="history-row"><div><a href="#practice/${a.question_id}">${e(questionById(a.question_id).title)} ↗</a><div><small>${dateText(a.submitted_at)} · ${typeNames[questionById(a.question_id).type]}${a.assisted?' · 参考后作答':''}</small></div><details><summary style="font-size:13px;cursor:pointer;color:var(--muted)">查看当时的回答</summary><div class="history-detail">${e(formatAnswer(a))}</div></details>${a.result==='pending'?`<button class="button ghost" data-assess="${e(a.id)}">继续这次自评</button>`:''}</div>${resultBadge(a)}</div>`).join(''):'<div class="empty"><h3>第一条记录，从一道题开始。</h3><p>提交答案后会自动保存在这里，不用另外写学习日志。</p><a class="button ghost" href="#practice">去练几道题 →</a></div>'}</section>
    <div class="section-heading"><h2>我的笔记</h2></div><section class="card">${Object.entries(data.state.notes).filter(([,text])=>text.trim()).map(([uid,text])=>`<div class="history-row"><div><a href="#learn/${uid}/0">${e(unitById(uid).title)}</a><div class="history-detail">${e(text)}</div></div></div>`).join('')||'<div class="empty"><p>学习页写下的一句话收获，会收在这里。</p></div>'}</section>
    <section class="card tools-card"><h3>把学习记录留在自己手里</h3><p>记录保存在这台电脑。备份包含课程、题目、笔记、草稿和作答；恢复会替换现有记录，并先保留一份旧备份。</p><div class="actions"><button class="button secondary" id="export-backup">导出完整备份</button><button class="button secondary" id="import-backup">恢复备份</button><input type="file" id="backup-file" accept=".json,application/json" hidden></div><div id="restore-area"></div></section>
    <section class="card tools-card"><h3>试用反馈</h3><p>记录你觉得难懂或不顺手的地方，导出后可以发回当前对话。不会自动发送。</p><div class="actions"><button class="button secondary" id="add-feedback">写一点反馈</button><button class="button ghost" id="export-feedback">导出反馈</button></div>${data.state.feedback.map(f=>`<div class="feedback-item"><small class="muted">${dateText(f.created_at)}</small><p>${e(f.text)}</p></div>`).join('')}</section>`;
  $('#review-feedback').addEventListener('click',()=>openFeedback());$('#add-feedback').addEventListener('click',()=>openFeedback());
  $('#review-mistakes').addEventListener('click',()=>{bankFilter='mistakes';navigate('practice');});
  document.querySelectorAll('[data-assess]').forEach(button=>action(button,async()=>{
    const attempt=data.state.attempts.find(a=>a.id===button.dataset.assess);
    await api('/api/resume-assessment/'+attempt.id,{});navigate('practice/'+attempt.question_id);
  }));
  action($('#export-backup'),async()=>{await flush();const backup=await api('/api/backup');download('软考虐待狂-学习备份.json',JSON.stringify(backup,null,2),'application/json');toast('备份已导出');});
  $('#import-backup').addEventListener('click',()=>$('#backup-file').click());
  $('#backup-file').addEventListener('change',async event=>{
    try {
      const file=event.target.files[0];if(!file)return;if(file.size>64_000_000)throw new Error('备份文件过大');
      const backup=JSON.parse(await file.text());const check=await api('/api/backup/check',backup);
      $('#restore-area').innerHTML=`<div class="restore-preview"><h3>确认恢复这份备份？</h3><p>${check.attempts} 次作答 · ${check.notes} 份笔记 · ${check.feedback} 条反馈。恢复将替换当前记录。</p><div class="actions"><button class="button danger" id="confirm-restore">确认替换并恢复</button><button class="button secondary" id="cancel-restore">取消</button></div></div>`;
      $('#cancel-restore').addEventListener('click',()=>$('#restore-area').replaceChildren());
      action($('#confirm-restore'),async()=>{await flush();await api('/api/backup/restore',backup);for(let i=localStorage.length-1;i>=0;i--){const key=localStorage.key(i);if(key.startsWith('zhixu:'))localStorage.removeItem(key);}toast('恢复成功，旧记录已另存备份');await render();});
    }catch(err){toast(err instanceof SyntaxError?'文件不是有效的 JSON 备份。':err.message,true);}
    finally{event.target.value='';}
  });
  action($('#export-feedback'),async()=>{await load();const text=data.state.feedback.map(f=>`${dateText(f.created_at)} / ${f.position}\n${f.text}`).join('\n\n---\n\n');if(!text)throw new Error('还没有反馈，可以先写一点。');download('软考虐待狂-试用反馈.txt',text,'text/plain');});
}

function download(name,content,type) {const url=URL.createObjectURL(new Blob([content],{type:type+';charset=utf-8'}));const link=document.createElement('a');link.href=url;link.download=name;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
function openFeedback(prefix='') {if(!$('#feedback-text').value)$('#feedback-text').value=prefix;$('#feedback-dialog').showModal();$('#feedback-text').focus();}
async function load(){const firstLoad=!data;data=await api('/api/bootstrap');[...data.pack.questions,...data.archive.questions].forEach(q=>questionCache.set(q.id,q));if(firstLoad){selectedMode=data.state.session?.mode||'learn';selectedTestUnit=data.state.session?.mode==='test'?data.state.session.unit_id:'';}}

async function render() {
  const sequence=++routeSequence;
  try{
    try{await flush();}catch(err){toast(err.message,true);}
    await load();if(sequence!==routeSequence)return;
    const raw=window.location.hash.slice(1)||'today';
    const [view,id,index]=raw.split('?')[0].split('/');
    document.querySelectorAll('[data-nav]').forEach(a=>{const active=a.dataset.nav===view;a.classList.toggle('active',active);if(active)a.setAttribute('aria-current','page');else a.removeAttribute('aria-current');});
    $('#breadcrumb').textContent='软件设计师 / '+({today:'今日学习',learn:'知识库',practice:'练习',review:'学习回顾',exams:'历年真题'}[view]||'今日学习');
    if(view==='learn'&&id)await renderLesson(id,index,sequence);
    else if(view==='learn')await renderLibrary(sequence);
    else if(view==='practice'&&id)await renderQuestion(id,sequence);
    else if(view==='practice')await renderBank(sequence);
    else if(view==='exams')await renderPapers(sequence,id);
    else if(view==='review')renderReview();
    else await renderToday();
    if((view==='learn'||view==='practice')&&id)await api('/api/position',{position:raw});
    window.scrollTo({top:0,behavior:'instant'});
  }catch(err){main.innerHTML=`<section class="card empty"><h2>暂时没有打开成功</h2><p>${e(err.message)}</p><button class="button primary" id="reload" style="margin-top:20px">重新连接</button></section>`;$('#reload').addEventListener('click',render);}
}

$('#open-feedback').addEventListener('click',()=>openFeedback());
$('#close-feedback').addEventListener('click',()=>$('#feedback-dialog').close());
$('#save-state').addEventListener('click',()=>flush().then(()=>toast('保存成功')).catch(err=>toast(err.message,true)));
const menuButton=$('#menu-button'),siteNav=$('#site-nav');
function closeMenu(returnFocus=false){document.body.classList.remove('menu-open');menuButton.setAttribute('aria-expanded','false');if(returnFocus)menuButton.focus();}
menuButton.addEventListener('click',()=>{const open=document.body.classList.toggle('menu-open');menuButton.setAttribute('aria-expanded',String(open));if(open)$('[data-nav]',siteNav).focus();});
siteNav.querySelectorAll('[data-nav]').forEach(link=>link.addEventListener('click',()=>closeMenu()));
document.addEventListener('keydown',event=>{if(event.key==='Escape'&&document.body.classList.contains('menu-open')){event.preventDefault();closeMenu(true);}});
window.addEventListener('resize',()=>{if(window.innerWidth>=720&&document.body.classList.contains('menu-open'))closeMenu();});
$('.skip-link').addEventListener('click',event=>{event.preventDefault();main.focus({preventScroll:true});main.scrollIntoView({block:'start'});});
$('#feedback-form').addEventListener('submit',async event=>{
  event.preventDefault();const button=$('button[type=submit]',event.target);button.disabled=true;
  try{await api('/api/feedback',{text:$('#feedback-text').value});$('#feedback-text').value='';$('#feedback-dialog').close();toast('反馈已保存在本机');if(window.location.hash==='#review')await render();}catch(err){toast(err.message,true);}finally{button.disabled=false;}
});
window.addEventListener('hashchange',render);
window.addEventListener('beforeunload',event=>{if(pending.size){event.preventDefault();event.returnValue='';}});
render();
