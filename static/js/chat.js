
(function(){
  const widget = document.getElementById('chat-widget');
  const toggle = document.getElementById('chat-toggle');
  const closeBtn = document.getElementById('chat-close');
  const input = document.getElementById('chat-text');
  const sendBtn = document.getElementById('chat-send');
  const messages = document.getElementById('chat-messages');
  let room = null, username='زائر';
  const socket = io();
  function pushMsg(sender, text){
    const div = document.createElement('div'); div.className='msg'+(sender===username?' you':''); 
    div.textContent=(sender==='system'?'🔔 ':'')+(sender!=='system'?sender+': ':'')+text; 
    messages.appendChild(div); messages.scrollTop=messages.scrollHeight;
  }
  socket.on('connected', ()=>{});
  socket.on('system', (d)=>pushMsg('system', d.text));
  socket.on('message', (d)=>pushMsg(d.sender||'مستخدم', d.text));
  function join(r){
    if(!r)return; room=r; socket.emit('join',{room});
    fetch('/api/messages/'+encodeURIComponent(room)).then(r=>r.json()).then(list=>list.forEach(m=>pushMsg(m.sender,m.text))).catch(()=>{});
  }
  window.openProductChat=function(productId, user){ username=user||'زائر'; join('product_'+productId); widget.classList.remove('hidden'); input.focus(); }
  toggle.addEventListener('click', ()=>{ widget.classList.toggle('hidden'); if(!room) join('lobby'); });
  closeBtn.addEventListener('click', ()=>widget.classList.add('hidden'));
  function send(){ const text=input.value.trim(); if(!text||!room) return; socket.emit('message',{room,text,sender:username}); input.value=''; }
  sendBtn.addEventListener('click', send); input.addEventListener('keydown', e=>{ if(e.key==='Enter') send(); });
})();
