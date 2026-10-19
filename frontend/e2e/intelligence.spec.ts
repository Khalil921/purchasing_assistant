import {test,expect} from './fixtures';

test('historical task deletion supports cancellation and preserves other tasks',async({page})=>{
 const keep=await (await page.request.post('/api/tasks',{data:{name:'保留的测试任务'}})).json();
 const remove=await (await page.request.post('/api/tasks',{data:{name:'将删除的测试任务'}})).json();
 await page.goto('/');
 await page.getByRole('button',{name:'删除任务 将删除的测试任务',exact:true}).click();
 const modal=page.getByRole('dialog',{name:'删除历史任务',exact:true});
 await expect(modal.getByText(/此操作无法撤销/)).toBeVisible();
 const desktopCancel=await modal.getByRole('button',{name:'取消',exact:true}).boundingBox();
 const desktopConfirm=await modal.getByRole('button',{name:'确认删除',exact:true}).boundingBox();
 expect(Math.abs(desktopCancel!.width-desktopConfirm!.width)).toBeLessThan(1);
 expect(desktopCancel!.height).toBe(desktopConfirm!.height);
 await page.screenshot({path:'../test-results/delete-dialog-desktop.png'});
 await page.setViewportSize({width:390,height:844});
 const confirmBounds=await modal.getByRole('button',{name:'确认删除',exact:true}).boundingBox();
 expect(confirmBounds!.width).toBeGreaterThan(90);
 expect(await modal.evaluate(el=>el.scrollWidth<=el.clientWidth)).toBe(true);
 await page.screenshot({path:'../test-results/delete-dialog-mobile.png'});
 await page.setViewportSize({width:1366,height:900});
 await modal.getByRole('button',{name:'取消',exact:true}).click();
 expect((await page.request.get('/api/tasks/'+remove.id)).status()).toBe(200);
 await page.getByRole('button',{name:'删除任务 将删除的测试任务',exact:true}).click();
 await modal.getByRole('button',{name:'确认删除',exact:true}).click();
 await expect(modal).toHaveCount(0);
 await expect(page.getByRole('button',{name:'删除任务 将删除的测试任务',exact:true})).toHaveCount(0);
 expect((await page.request.get('/api/tasks/'+remove.id)).status()).toBe(404);
 expect((await page.request.get('/api/tasks/'+keep.id)).status()).toBe(200);
 await page.screenshot({path:'../test-results/task-deletion.png',fullPage:true});
});

test('old backend deletion error is explained inside confirmation dialog',async({page})=>{
 const t=await (await page.request.post('/api/tasks',{data:{name:'旧版接口提示测试'}})).json();
 await page.route(`**/api/tasks/${t.id}`,async route=>{
  if(route.request().method()==='DELETE')await route.fulfill({status:405,json:{detail:'Method Not Allowed'}});
  else await route.continue();
 });
 await page.goto('/');
 await page.getByRole('button',{name:'删除任务 旧版接口提示测试',exact:true}).click();
 const modal=page.getByRole('dialog',{name:'删除历史任务',exact:true});
 await modal.getByRole('button',{name:'确认删除',exact:true}).click();
 await expect(modal.getByRole('alert')).toContainText('可能仍在运行旧版本');
 expect((await page.request.get('/api/tasks/'+t.id)).status()).toBe(200);
 await modal.getByRole('button',{name:'取消',exact:true}).click();
});

test('AI engine explains provenance and displays mocked semantic evidence and human review',async({page})=>{
 let task=await (await page.request.post('/api/samples/A')).json();
 await page.request.post(`/api/tasks/${task.id}/confirm-fields`);
 task=await (await page.request.post(`/api/tasks/${task.id}/audit`)).json();
 await page.goto('/');
 await expect(page.getByText('① AI 文档理解',{exact:true})).toBeVisible();
 await page.getByRole('button',{name:'打开 AI 语义复核',exact:true}).click();
 const modal=page.getByRole('dialog',{name:'AI 语义复核',exact:true});
 await expect(modal.getByRole('button',{name:'开始 AI 语义复核',exact:true})).toBeDisabled();
 await page.keyboard.press('Escape');
 await page.route('**/api/config',route=>route.fulfill({json:{mode:'测试配置',configured:true}}));
 const d=task.documents[0],b=d.blocks[0];
 const citation={document_id:d.id,document:d.name,location:b.location,quote:b.text};
 await page.route(`**/api/tasks/${task.id}/ai-analysis`,async route=>{
  task={...task,ai_analysis:{status:'已完成',model:'browser-test-mock',call_id:'mock-call',summary:'模拟响应：请核实交付基准',summary_evidence:[citation],limitations:['模拟响应仅验证界面，不代表模型准确率。'],findings:[{id:'AI-01',title:'基准事件需要确认',category:'交付语义',severity:'低',explanation:'此为浏览器测试模拟建议。',suggestion:'核对业务要求。',evidence:[citation],related_issue_ids:[],status:'待处理',note:''}]}};
  await route.fulfill({json:task});
 });
 await page.route(`**/api/tasks/${task.id}/ai-findings/AI-01`,async route=>{
  const body=route.request().postDataJSON();expect(body).toEqual({status:'已确认',note:'测试人工确认'});
  task.ai_analysis.findings[0]={...task.ai_analysis.findings[0],...body};await route.fulfill({json:task});
 });
 await page.reload();
 await page.getByRole('button',{name:'打开 AI 语义复核',exact:true}).click();
 await modal.getByRole('button',{name:'开始 AI 语义复核',exact:true}).click();
 await expect(modal.getByText('模拟响应：请核实交付基准',{exact:true})).toBeVisible();
 await modal.getByRole('button',{name:'查看完整原文'}).first().click();
 await expect(page.getByRole('dialog',{name:'文档原文',exact:true})).toBeVisible();
 await page.keyboard.press('Escape');
 await modal.locator('select').selectOption('已确认');
 await modal.getByRole('textbox',{name:'AI 建议处理备注'}).fill('测试人工确认');
 await modal.getByRole('button',{name:'保存 AI 建议判断'}).click();
 await expect(modal.locator('.ai-finding .tag')).toContainText('已确认');
 await page.screenshot({path:'../test-results/ai-semantic-review.png',fullPage:true});
});
