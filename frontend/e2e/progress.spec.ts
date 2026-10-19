import {test,expect} from './fixtures';
test('floating progress opens logs, minimizes and closes after completion',async({page})=>{
 await page.goto('/');
 await page.getByRole('button',{name:'演示中心',exact:true}).click();
 await page.getByRole('button',{name:'载入 A 组 · 一致'}).click();
 let finish!:()=>void;
 const delayed=new Promise<void>(resolve=>{finish=resolve});
 await page.route('**/api/tasks/*/extract',async route=>{await delayed;await route.continue()});
 try{
  await page.getByRole('button',{name:'提取关键信息'}).click();
  const progress=page.getByRole('dialog',{name:'处理进度',exact:true});
  await expect(progress).toBeVisible();
  await expect(progress.getByRole('heading',{name:'正在抽取关键信息'})).toBeVisible();
  await expect(progress.getByText('收起窗口不会中断任务，处理结束后自动关闭。')).toBeVisible();
  await page.screenshot({path:'../test-results/progress-window.png',fullPage:true});
  await progress.getByRole('button',{name:'查看调用记录'}).click();
  const logs=page.getByRole('dialog',{name:'模型调用记录',exact:true});
  await expect(logs).toBeVisible();
  await expect(logs.getByRole('status')).toContainText('任务仍在处理中');
  await page.keyboard.press('Escape');
  const floating=page.getByRole('complementary',{name:'后台处理进度'});
  await expect(floating).toBeVisible();
  await floating.getByRole('button',{name:'展开',exact:true}).click();
  await expect(progress).toBeVisible();
  await page.setViewportSize({width:390,height:844});
  await page.screenshot({path:'../test-results/progress-mobile.png',fullPage:true});
  await progress.getByRole('button',{name:'收起进度窗'}).click();
  await expect(floating).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  finish();
  await expect(floating).toHaveCount(0);
  await expect(progress).toHaveCount(0);
  await page.getByRole('button',{name:'调用记录',exact:true}).click();
  await expect(logs.locator('.log-table tbody tr')).toHaveCount(3);
 }finally{finish()}
});
