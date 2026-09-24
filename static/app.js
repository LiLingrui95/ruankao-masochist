'use strict';
const $ = (selector, root = document) => root.querySelector(selector);
const main = $('#main');
let data, routeSequence = 0, selectedBudget = 25, bankFilter = 'all';
let saveTimer, saveChain = Promise.resolve();
const pending = new Map();
const typeNames = {single_choice: '选择题', short_answer: '简答题', code_fill: '代码题'};
const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const e = escapeHtml;
const unitById = id => [...data.pack.units,...data.archive.units].find(u => u.id === id);
const questionById = id => [...data.pack.questions,...data.archive.questions].find(q => q.id === id);
const unitQuestions = id => [...data.pack.questions,...data.archive.questions].filter(q => q.unit_id === id);
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

function saveStatus(text, error = false) { const node = $('#save-state'); node.textContent = text; node.classList.toggle('error',error); }
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
function taskTitle(task) {return task.kind === 'lesson' ? data.sections[task.unit_id][task.section].title : questionById(task.question_id).title;}
function navigate(target) {if (window.location.hash.slice(1) === target) render(); else window.location.hash = target;}
function completion(uid) {return data.state.units[uid]?.read_sections?.length || 0;}
function heading(title, subtitle, side = '') {return `<div class="page-heading"><div><div class="eyebrow">考试专题 / 第一阶段</div><h1>${title}</h1>${subtitle ? `<p>${subtitle}</p>` : ''}</div>${side}</div>`;}

function unitsGrid() {
  return `<div class="unit-grid">${data.pack.units.map((u,i) => {
    const answered = unitQuestions(u.id).filter(q=>data.summary.latest[q.id]).length;
    const read = completion(u.id);
    return `<article class="card unit-card"><div class="unit-card-top"><span class="unit-index">0${i+1}</span><span class="pill ${data.summary.unit_checked[u.id] ? '' : 'gray'}">${data.summary.unit_checked[u.id] ? '检查已通过' : u.tag}</span></div><h3><a href="#learn/${u.id}/0">${e(u.title)}</a></h3><p>${e(u.subtitle)}</p><div class="progress" aria-label="已读 ${read} 个小节"><span style="width:${read/data.sections[u.id].length*100}%"></span></div><div class="unit-card-bottom"><span>已读 ${read}/${data.sections[u.id].length} · 已练 ${answered}/${unitQuestions(u.id).length}</span><a href="#learn/${u.id}/0">进入单元 ↗</a></div></article>`;
  }).join('')}</div>`;
}

function renderToday() {
  const task = nextTask();
  const uid = task?.unit_id || (task?.question_id ? questionById(task.question_id).unit_id : null)
    || data.pack.units.find(u => data.summary.eligible[u.id] && !data.summary.unit_checked[u.id])?.id || data.pack.units[0].id;
  const u = unitById(uid), unitIndex = data.pack.units.indexOf(u)+1;
  const session = data.state.session;
  const done = session?.completed_at && session.tasks.length;
  const today = new Date();
  const parts = data.state.position.split('/');
  const validPosition = parts[0]==='learn' ? !!data.sections[parts[1]]?.[Number(parts[2])] : parts[0]==='practice' && !!questionById(parts[1]);
  const resume = validPosition ? data.state.position : '';
  main.innerHTML = heading('今天，攻克一个考点。','从真题要求出发，理解、推导，再用练习检验。',`<div class="date-stamp"><strong>${today.toLocaleDateString('en-GB',{day:'2-digit',month:'short'})}</strong>${today.toLocaleDateString('zh-CN',{weekday:'long'})}</div>`)
    + `<div class="dashboard-grid"><section class="card focus-card"><span class="unit-number">0${unitIndex}</span><span class="pill">${done ? '这一组已完成' : task ? '接着上次' : '建议从这里开始'}</span><h2>${done ? '今天的这一小步，完成了。' : e(u.title)}</h2><p>${done ? '可以在这里停下，也可以再选一组任务。你的学习记录已经保存。' : task ? e(taskTitle(task)) : e(u.subtitle)}</p><div class="actions"><button class="button primary" id="start-session">${task ? '继续今日任务' : done ? '再学一组' : '开始今天的学习'} <span>→</span></button><a class="button ghost" href="#learn">查看全部单元</a></div></section>
    <section class="card session-card"><h3>${task ? '这一组学习任务' : '这次，留一点时间给自己'}</h3><div class="budget-options" aria-label="本次学习时间">${[10,25,45].map(n=>`<button data-budget="${n}" class="${selectedBudget===n?'selected':''}" aria-pressed="${selectedBudget===n}">${n} 分钟</button>`).join('')}</div><div id="task-preview">${task ? session.tasks.map(t=>`<div class="task-row"><span class="step ${t.done?'done':''}">${t.done?'✓':t.kind==='lesson'?'读':'练'}</span><div>${e(taskTitle(t))}<small>约 ${t.minutes} 分钟</small></div></div>`).join('') : `<div class="task-row"><span class="step">1</span><div>理解一个小概念<small>短讲解 + 逐步示例</small></div></div><div class="task-row"><span class="step">2</span><div>用练习检查理解<small>先作答，再看解析</small></div></div><div class="task-row"><span class="step">3</span><div>留下一点收获<small>记录自动保存，笔记随意</small></div></div>`}</div>${task?'<small class="muted">新时长用于下一组，当前任务可以继续。</small>':''}</section></div>
    ${resume ? `<div class="actions"><a class="button ghost" href="#${e(resume)}">回到上次阅读 / 答题的位置 ↗</a></div>` : ''}
    <div class="section-heading"><h2>当前考试专题</h2><a href="#practice">24 道对标练习 ↗</a></div>${unitsGrid()}
    <div class="stats-strip"><div class="stat"><strong>${data.summary.answered}<small> / 24</small></strong><span>已练习题目</span></div><div class="stat"><strong>${data.summary.first_total ? data.summary.first_correct+'/'+data.summary.first_total : '—'}</strong><span>首次独立选择题答对</span></div><div class="stat"><strong>${data.summary.mistakes.length}</strong><span>待巩固题目</span></div></div>`;
  document.querySelectorAll('[data-budget]').forEach(b=>b.addEventListener('click',()=>{selectedBudget=Number(b.dataset.budget);renderToday();}));
  action($('#start-session'),async()=>{
    await flush();
    const session = await api('/api/session',{budget:selectedBudget});
    const task = session.tasks.find(t=>!t.done);
    if (task) navigate(taskLocation(task));
    else {toast('三课任务已完成，可以在练习页继续巩固。');navigate('practice');}
  });
}

function renderLibrary() {
  main.innerHTML = heading('按考试要求，重建知识。','已具备编程基础，从计算、算法和关系建模进入。每单元四小节、八题，可自由选择。')+unitsGrid()+`<section class="card tools-card"><h3>为什么调整这三课？</h3><p>公开历年题目要求解释模型、完成多步计算、补全算法和设计关系模式。新版增加考点应用与综合推导；不是整套真题，也不代表全部考纲已覆盖。</p><a href="https://www.cnitpm.com/pm1/140332.html" target="_blank" rel="noopener noreferrer">综合知识题干样本 ↗</a> · <a href="https://www.cnitpm.com/pm1/140456.html" target="_blank" rel="noopener noreferrer">应用技术题干样本 ↗</a></section><section class="card tools-card"><h3>后续学习路线</h3><p>以下为待制作单元，当前先验证前三专题的难度与节奏。</p><div class="roadmap">${data.pack.roadmap.map(item=>`<div><span>${String(item.number).padStart(2,'0')}</span><strong>${e(item.title)}</strong><small>待制作</small></div>`).join('')}</div></section><details class="card tools-card"><summary>旧版编程基础 · 选读归档</summary><p>旧课程、答案和笔记继续保留，不计入新版 24 题进度。</p>${data.archive.units.map(u=>`<p><a href="#learn/${u.id}/0">${e(u.title)} ↗</a> · <a href="#practice?unit=${u.id}">旧版练习</a></p>`).join('')}</details>`;
}

function sources(uid) {
  const u = unitById(uid);
  return `<details class="sources"><summary>资料来源与内容说明</summary>${[...data.pack.sources,...data.archive.sources].filter(s=>u.source_ids.includes(s.id)).map(s=>`<a href="${e(s.url)}" target="_blank" rel="noopener noreferrer">${e(s.title)} ↗</a>`).join('')}<p>讲解与练习为原创。真题转录用于对照考查方式，网站解析不是官方标准答案；技术文档和教材用于核验与延伸学习。难度为编辑判断，等待试用反馈。内容版本 ${e(u.version)}。</p></details>`;
}

function renderLesson(uid, index) {
  const u = unitById(uid); if (!u) throw new Error('单元不存在');
  const sections = data.sections[uid]; index = Number(index || 0);
  if (!sections[index]) index=0;
  const s=sections[index], progress=data.state.units[uid]?.read_sections||[];
  const missing = u.prerequisite_ids.filter(id=>!data.summary.unit_checked[id]&&!data.state.units[id]?.override);
  main.innerHTML = heading(e(u.title),e(u.subtitle),`<a class="button secondary" href="#practice?unit=${uid}">直接练习 ↗</a>`)
    + `${missing.length ? `<div class="notice">这课会用到「${missing.map(id=>e(unitById(id).title)).join('、')}」的知识。你仍可自由阅读。<div class="actions"><a class="button ghost" href="#learn/${missing[0]}/0">先回顾上一课</a><button class="button secondary" id="override">我已了解先修内容，跳过检查</button></div></div>`:''}`
    + `<div class="learn-layout"><div><article class="card reading-card"><div class="reading-top"><span class="pill">小节 ${index+1} / ${sections.length}</span><span>约 ${s.minutes} 分钟 ${progress.includes(index)?'· 已读':''}</span></div><h2 class="lesson-title">${e(s.title)}</h2><div class="prose">${s.html}</div><div class="reading-nav"><a class="button ghost" href="#learn/${uid}/${Math.max(0,index-1)}">${index?'← 上一小节':'回到本课开头'}</a><button class="button primary" id="finish-section">${nextTask()?'读完了，继续任务':index<sections.length-1?'读完了，下一小节':'读完了，做几道题'} →</button></div></article>
    <section class="card note-card"><label for="lesson-note">一句话收获 <span class="muted">/ 想记就记</span></label><textarea id="lesson-note" rows="3" maxlength="15000" placeholder="用自己的话记下一点理解，或暂时没想明白的问题。"></textarea><span class="saved-label" id="note-status">输入后自动保存</span></section>${sources(uid)}</div>
    <aside class="lesson-aside"><div class="card toc"><div class="eyebrow">本课目录</div>${sections.map((sec,i)=>`<a href="#learn/${uid}/${i}" class="${i===index?'active':''}"><span>${progress.includes(i)?'✓':String(i+1).padStart(2,'0')}</span>${e(sec.title)}</a>`).join('')}</div><div class="objectives"><h3>学完，你可以</h3><ul>${u.objectives.map(o=>`<li>${e(o)}</li>`).join('')}</ul><button class="button ghost" id="lesson-feedback">这段内容有疑问？</button></div></aside></div>`;
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
function renderBank() {
  const params=new URLSearchParams(window.location.hash.split('?')[1]||'');
  if(params.get('unit')&&unitById(params.get('unit'))) bankFilter=params.get('unit');
  let questions=bankFilter.startsWith('CSF-')?data.archive.questions:data.pack.questions;
  if(bankFilter==='mistakes') questions=questions.filter(q=>data.summary.mistakes.includes(q.id));
  else if(bankFilter!=='all') questions=questions.filter(q=>q.unit_id===bankFilter);
  main.innerHTML=heading('用练习，检查理解。','先独立想一想。简答和代码题提交后，按要点对照自评。')+`<div class="filter-row">${[['all','全部 24 题'],...data.pack.units.map(u=>[u.id,u.title]),['mistakes','错题与不确定']].map(([id,label])=>`<button data-filter="${id}" class="${bankFilter===id?'active':''}">${e(label)}</button>`).join('')}</div><div class="card question-list">${questions.length?questions.map(q=>{
    const a=data.summary.latest[q.id];
    return `<a class="question-list-row" href="#practice/${q.id}"><span class="q-number">${q.id.slice(-2)}</span><div><h3>${e(q.title)}</h3><p>${e(unitById(q.unit_id).title)} · ${typeNames[q.type]} · ${e(q.difficulty||'旧版基础')} · 约 ${q.minutes} 分钟</p></div>${a?resultBadge(a):'<span class="pill gray">未练习 ↗</span>'}</a>`;
  }).join(''):`<div class="empty"><h3>这里暂时没有题目</h3><p>做错或标记“不确定”的题目会出现在这里。</p></div>`}</div>`;
  document.querySelectorAll('[data-filter]').forEach(b=>b.addEventListener('click',()=>{bankFilter=b.dataset.filter;history.replaceState(null,'','#practice');renderBank();}));
}

async function renderQuestion(qid, sequence) {
  const response=await api('/api/question/'+qid);if(sequence!==routeSequence)return;
  const q=response.question,u=unitById(q.unit_id),key='draft:'+qid;
  if(response.attempt) cacheRemove(key);
  const cached=response.attempt?null:cacheGet(key);
  const draft=cached||response.draft||{answer:{},uncertain:false,submission_key:crypto.randomUUID()};
  let attempt=response.attempt;
  const fields=q.type==='single_choice'?Object.entries(q.options).map(([id,label])=>`<label class="option"><input type="radio" name="option" value="${id}" ${draft.answer.option===id?'checked':''}><span class="option-key">${id}</span><span>${e(label)}</span></label>`).join('')
    :q.type==='short_answer'?`<div class="answer-fields"><label for="answer-text">你的回答</label><textarea id="answer-text" rows="6" maxlength="15000" placeholder="先用自己的话写出思路，不需要与参考答案一字不差。">${e(draft.answer.text||'')}</textarea></div>`
    :`<div class="answer-fields"><label for="answer-blank">空白处填写</label><input type="text" id="answer-blank" maxlength="15000" autocomplete="off" spellcheck="false" placeholder="多处填空请按编号依次填写" value="${e(draft.answer.blank||'')}"><label for="answer-explanation">结果与推导</label><textarea id="answer-explanation" rows="4" maxlength="15000" placeholder="写出结果、推导过程，以及题目要求的复杂度或边界解释。">${e(draft.answer.explanation||'')}</textarea></div>`;
  main.innerHTML=heading(e(u.title),'每次作答都是一次检查，拿不准也可以如实记录。',`<a class="button secondary" href="#learn/${u.id}/0">回看讲解</a>`)+`<div class="question-layout"><section class="card question-card"><div class="question-meta"><span>${typeNames[q.type]} · ${e(q.difficulty||'旧版基础')}</span><span>${e(q.id)}</span></div><h2>${e(q.title)}</h2>${q.exam_anchor?`<p class="exam-anchor">${e(q.exam_anchor)} · 原创对标练习${q.language?' · '+e(q.language.toUpperCase()):''}</p>`:''}<p class="question-prompt">${e(q.prompt)}</p>${q.code?`<pre class="question-code"><code>${e(q.code)}</code></pre>`:''}<form id="answer-form"><fieldset style="border:0;padding:0;margin:0" ${attempt?'disabled':''}><legend class="sr-only" style="position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0,0,0,0)">填写答案</legend>${fields}<label class="uncertain"><input id="uncertain" type="checkbox" ${draft.uncertain?'checked':''}>不太确定 / 这次有猜测</label></fieldset>${!attempt?'<div class="answer-actions"><button class="button primary" type="submit" id="submit-answer">提交答案</button><button type="button" class="button ghost" id="reveal-answer">先看看解析</button></div>':''}</form><div id="reference"></div><div class="answer-actions" id="after-actions" ${attempt?'':'hidden'}><button class="button primary" id="next-question">继续 →</button><button class="button secondary" id="retry-question">重新作答</button><a class="button ghost" href="#practice">返回题目列表</a></div></section><aside><div class="card question-map"><h3>本课练习</h3><div class="map-grid">${unitQuestions(q.unit_id).map((item,i)=>`<a href="#practice/${item.id}" class="${item.id===q.id?'active':data.summary.latest[item.id]?'completed':''}">${i+1}</a>`).join('')}</div><p>选择题自动反馈。简答与代码题按要点自评。</p></div>${sources(u.id)}</aside></div>`;
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
    + `<div class="review-stats"><div class="card metric"><p>已读完的单元</p><strong>${completed}<small> / 3</small></strong><small>读完与通过检查分别记录</small></div><div class="card metric"><p>首次独立选择题答对</p><strong>${s.first_total?s.first_correct+' / '+s.first_total:'—'}</strong><small>参考后作答、主观题不混入</small></div><div class="card metric"><p>待巩固题目</p><strong>${s.mistakes.length}</strong><small>最新做错或标记不确定</small></div></div>
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
      const file=event.target.files[0];if(!file)return;if(file.size>8_000_000)throw new Error('备份文件过大');
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
async function load(){const firstLoad=!data;data=await api('/api/bootstrap');if(firstLoad)selectedBudget=data.state.budget;}

async function render() {
  const sequence=++routeSequence;
  try{
    try{await flush();}catch(err){toast(err.message,true);}
    await load();if(sequence!==routeSequence)return;
    const raw=window.location.hash.slice(1)||'today';
    const [view,id,index]=raw.split('?')[0].split('/');
    document.querySelectorAll('[data-nav]').forEach(a=>a.classList.toggle('active',a.dataset.nav===view));
    $('#breadcrumb').textContent='第一阶段 / '+({today:'今日学习',learn:'知识单元',practice:'练习',review:'学习回顾'}[view]||'今日学习');
    if(view==='learn'&&id)renderLesson(id,index);
    else if(view==='learn')renderLibrary();
    else if(view==='practice'&&id)await renderQuestion(id,sequence);
    else if(view==='practice')renderBank();
    else if(view==='review')renderReview();
    else renderToday();
    if((view==='learn'||view==='practice')&&id)await api('/api/position',{position:raw});
    window.scrollTo({top:0,behavior:'instant'});
  }catch(err){main.innerHTML=`<section class="card empty"><h2>暂时没有打开成功</h2><p>${e(err.message)}</p><button class="button primary" id="reload" style="margin-top:20px">重新连接</button></section>`;$('#reload').addEventListener('click',render);}
}

$('#open-feedback').addEventListener('click',()=>openFeedback());
$('#close-feedback').addEventListener('click',()=>$('#feedback-dialog').close());
$('#save-state').addEventListener('click',()=>flush().then(()=>toast('保存成功')).catch(err=>toast(err.message,true)));
$('#feedback-form').addEventListener('submit',async event=>{
  event.preventDefault();const button=$('button[type=submit]',event.target);button.disabled=true;
  try{await api('/api/feedback',{text:$('#feedback-text').value});$('#feedback-text').value='';$('#feedback-dialog').close();toast('反馈已保存在本机');if(window.location.hash==='#review')await render();}catch(err){toast(err.message,true);}finally{button.disabled=false;}
});
window.addEventListener('hashchange',render);
window.addEventListener('beforeunload',event=>{if(pending.size){event.preventDefault();event.returnValue='';}});
render();
