import {test as base,expect} from '@playwright/test';
export const test=base.extend({page:async({page},use)=>{
 const r=await page.request.post('/api/auth/login',{data:{username:'OS-HUBU',password:'e2e-only-password'}});
 expect(r.ok()).toBeTruthy();
 await use(page);
}});
export {expect};
