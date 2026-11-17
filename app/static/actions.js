const pharmacy={pending:false,plan:JSON.parse(document.getElementById('plan').textContent)};
const message=document.getElementById('message');
async function savePlan(endpoint,body,targetMessage){
  if(pharmacy.pending)return;
  pharmacy.pending=true;
  const box=targetMessage||message;
  if(box)box.textContent='正在安排批号…';
  for(const b of document.querySelectorAll('button'))b.disabled=true;
  try{
    let request={method:'POST',body:body};
    if(!(body instanceof FormData)){
      request.body=JSON.stringify(body);
      request.headers={'Content-Type':'application/json'};
    }
    let response=await fetch(endpoint,request),result=await response.json();
    if(response.status>=400)throw Error(result.message);
    if(result.manifest){
      location.href=location.pathname+'?run_id='+encodeURIComponent(result.manifest.run_id);
    }else{
      location.reload();
    }
  }catch(e){
    if(box)box.textContent=e.message||'提交失败，请重试';
  }finally{
    pharmacy.pending=false;
    for(const b of document.querySelectorAll('button'))b.disabled=false;
  }
}
document.getElementById('demo').addEventListener('click',()=>savePlan('/api/run',{}));
document.getElementById('commit').addEventListener('click',()=>savePlan('/api/run',{csv:document.getElementById('source').value}));
document.getElementById('sendfile').addEventListener('click',()=>{
  let f=document.getElementById('attachment').files[0];
  if(!f){message.textContent='先选择库存文件。';return}
  let data=new FormData();data.append('file',f);
  savePlan('/api/run',data);
});
document.querySelectorAll('[data-approve]').forEach(el=>el.addEventListener('click',()=>savePlan('/api/review',{...pharmacy.plan,decision:el.dataset.approve})));
document.getElementById('paper').addEventListener('click',()=>window.print());

const revisionButton=document.getElementById('revision-commit');
if(revisionButton){
  revisionButton.addEventListener('click',()=>{
    const box=document.getElementById('revision-message');
    const idem=document.getElementById('idem-key').value.trim();
    const body={csv:document.getElementById('revision-source').value,parent_id:pharmacy.plan.id};
    if(idem)body.idempotency_key=idem;
    pharmacy.pending=false;
    savePlan('/api/revision',body,box);
  });
}
