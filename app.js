const STORAGE_KEY = 'triple20_dartvision_lab_v2';
const BOARD_COUNT = 4;
const startScoreSelect = document.querySelector('#startScore');
const bestOfSelect = document.querySelector('#bestOf');
const boardsElement = document.querySelector('#boards');
const template = document.querySelector('#boardTemplate');

function newBoard(index, startScore = 501, bestOf = 3) {
  return { id:index+1, names:{a:'',b:''}, remaining:{a:startScore,b:startScore}, legs:{a:0,b:0}, active:'a', visitStart:startScore, currentVisit:[], lastVisit:null, editing:null, startScore, bestOf, winner:null, history:[], darts:[] };
}
function newSession() {
  const startScore=Number(startScoreSelect.value), bestOf=Number(bestOfSelect.value);
  return { schemaVersion:2, createdAt:new Date().toISOString(), startScore, bestOf, boards:Array.from({length:BOARD_COUNT},(_,i)=>newBoard(i,startScore,bestOf)) };
}
function loadSession() {
  try { const saved=JSON.parse(localStorage.getItem(STORAGE_KEY)); if(saved?.schemaVersion===2&&saved?.boards?.length===BOARD_COUNT)return saved; }
  catch(error){ console.warn('Lokale Testdaten konnten nicht gelesen werden.',error); }
  return newSession();
}
let session=loadSession();
startScoreSelect.value=String(session.startScore||501); bestOfSelect.value=String(session.bestOf||3);
const saveSession=()=>localStorage.setItem(STORAGE_KEY,JSON.stringify(session));
const displayName=(board,player)=>board.names[player].trim()||`Spieler ${player==='a'?'1':'2'}`;
const legsNeeded=board=>Math.ceil(board.bestOf/2);

function createDart(segment,multiplier){
  if(segment===0)return {segment:0,multiplier:0,score:0,label:'MISS'};
  if(segment===25){const m=multiplier===2?2:1;return {segment:25,multiplier:m,score:25*m,label:m===2?'BULL':'25'};}
  const prefix=multiplier===3?'T':multiplier===2?'D':'S';
  return {segment,multiplier,score:segment*multiplier,label:`${prefix}${segment}`};
}
function snapshot(board){return JSON.stringify({remaining:board.remaining,legs:board.legs,active:board.active,visitStart:board.visitStart,currentVisit:board.currentVisit,winner:board.winner,darts:board.darts});}
function finishTurn(board){board.active=board.active==='a'?'b':'a';board.visitStart=board.remaining[board.active];board.currentVisit=[];}
function rememberCompletedVisit(board,player,darts){board.lastVisit={player,darts:darts.map(d=>({...d})),historyStartIndex:board.history.length-darts.length};}

function recordDart(board,dart){
  if(board.winner)return {ok:false,message:'Dieses Match ist bereits beendet.'};
  if(board.currentVisit.length===0&&board.lastVisit)board.lastVisit=null;
  board.history.push(snapshot(board));
  const player=board.active, next=board.remaining[player]-dart.score;
  board.currentVisit.push(dart); board.darts.push({...dart,player,at:new Date().toISOString()});
  const invalidCheckout=next===0&&dart.multiplier!==2;
  if(next<0||next===1||invalidCheckout){
    const completed=board.currentVisit.map(d=>({...d})); board.remaining[player]=board.visitStart; finishTurn(board); rememberCompletedVisit(board,player,completed);
    return {ok:true,message:invalidCheckout?'Bust – Checkout muss auf einem Doppel erfolgen.':'Bust – Aufnahme wird zurückgesetzt.'};
  }
  board.remaining[player]=next;
  if(next===0){
    board.legs[player]++;
    const completed=board.currentVisit.map(d=>({...d}));
    if(board.legs[player]>=legsNeeded(board)){board.winner=player;board.currentVisit=[];rememberCompletedVisit(board,player,completed);return {ok:true,message:`${displayName(board,player)} gewinnt das Match.`};}
    board.remaining={a:board.startScore,b:board.startScore}; board.active=player==='a'?'b':'a'; board.visitStart=board.startScore; board.currentVisit=[];
    rememberCompletedVisit(board,player,completed);
    return {ok:true,message:`${displayName(board,player)} gewinnt das Leg.`};
  }
  if(board.currentVisit.length===3){const completed=board.currentVisit.map(d=>({...d}));finishTurn(board);rememberCompletedVisit(board,player,completed);}
  return {ok:true,message:''};
}
function undo(board){const saved=board.history.pop();if(!saved)return false;Object.assign(board,JSON.parse(saved));return true;}
function editDart(board,scope,index,replacement){
  const source=scope==='last'?board.lastVisit?.darts:board.currentVisit;
  if(!source?.[index])return false;
  const darts=source.map((dart,i)=>i===index?replacement:{...dart});
  const startIndex=scope==='last'?board.lastVisit.historyStartIndex:board.history.length-board.currentVisit.length;
  const base=board.history[startIndex]; if(!base)return false;
  const priorHistory=board.history.slice(0,startIndex);
  Object.assign(board,JSON.parse(base)); board.history=priorHistory; board.lastVisit=null; board.editing=null;
  darts.forEach(dart=>recordDart(board,dart));
  return true;
}

function render(){
  boardsElement.replaceChildren();
  session.boards.forEach((board,index)=>{
    const fragment=template.content.cloneNode(true), root=fragment.querySelector('.board'); root.dataset.boardIndex=String(index);
    fragment.querySelector('.board-number').textContent=`BOARD ${board.id}`; fragment.querySelector('.board-title').textContent=`Testboard ${board.id}`;
    fragment.querySelector('.player-a-name').value=board.names.a; fragment.querySelector('.player-b-name').value=board.names.b;
    fragment.querySelector('.player-a-label').textContent=displayName(board,'a'); fragment.querySelector('.player-b-label').textContent=displayName(board,'b');
    fragment.querySelector('.player-a-score').textContent=board.remaining.a; fragment.querySelector('.player-b-score').textContent=board.remaining.b;
    fragment.querySelector('.player-a-legs').textContent=board.legs.a; fragment.querySelector('.player-b-legs').textContent=board.legs.b;
    fragment.querySelector('.current-player').textContent=displayName(board,board.active); fragment.querySelector('.dart-number').textContent=String(board.currentVisit.length+1);
    fragment.querySelector(`[data-player="${board.active}"]`).classList.add('active'); fragment.querySelector(`[data-player="${board.active==='a'?'b':'a'}"]`).classList.remove('active');
    const darts=fragment.querySelector('.visit-darts');
    board.currentVisit.forEach((dart,i)=>{const chip=document.createElement('button');chip.type='button';chip.className='dart-chip edit-dart';chip.dataset.scope='current';chip.dataset.dartIndex=String(i);chip.textContent=dart.label;darts.append(chip);});
    fragment.querySelector('.visit-total').textContent=`${board.currentVisit.reduce((sum,d)=>sum+d.score,0)} Punkte`;
    if(board.lastVisit){
      const lastBox=fragment.querySelector('.last-visit'),lastDarts=fragment.querySelector('.last-visit-darts');lastBox.hidden=false;
      board.lastVisit.darts.forEach((dart,i)=>{const chip=document.createElement('button');chip.type='button';chip.className='dart-chip edit-dart';chip.dataset.scope='last';chip.dataset.dartIndex=String(i);chip.textContent=dart.label;lastDarts.append(chip);});
    }
    if(board.editing){
      const source=board.editing.scope==='last'?board.lastVisit?.darts:board.currentVisit,dart=source?.[board.editing.index];
      if(dart){fragment.querySelector('.segment-input').value=String(dart.segment);fragment.querySelector('.multiplier-input').value=String(dart.multiplier||1);fragment.querySelector('.add-dart').textContent='Änderung speichern';fragment.querySelector('.cancel-edit').hidden=false;fragment.querySelector(`.edit-dart[data-scope="${board.editing.scope}"][data-dart-index="${board.editing.index}"]`)?.classList.add('editing');}
    }
    fragment.querySelector('.status').textContent=board.winner?`${displayName(board,board.winner)} gewinnt`:'Bereit'; boardsElement.append(fragment);
  });
}
boardsElement.addEventListener('input',event=>{
  const root=event.target.closest('.board'); if(!root||!event.target.classList.contains('player-name'))return;
  const board=session.boards[Number(root.dataset.boardIndex)], player=event.target.classList.contains('player-a-name')?'a':'b';
  board.names[player]=event.target.value;saveSession();root.querySelector(`.player-${player}-label`).textContent=displayName(board,player);if(board.active===player)root.querySelector('.current-player').textContent=displayName(board,player);
});
boardsElement.addEventListener('submit',event=>{
  if(!event.target.classList.contains('throw-form'))return;event.preventDefault();
  const root=event.target.closest('.board'),board=session.boards[Number(root.dataset.boardIndex)];
  const dart=createDart(Number(event.target.querySelector('.segment-input').value),Number(event.target.querySelector('.multiplier-input').value));
  if(board.editing){const changed=editDart(board,board.editing.scope,board.editing.index,dart);if(changed){saveSession();render();}else root.querySelector('.message').textContent='Dieser Dart konnte nicht mehr geändert werden.';return;}
  const result=recordDart(board,dart);
  if(result.ok){saveSession();render();boardsElement.querySelector(`[data-board-index="${root.dataset.boardIndex}"] .message`).textContent=result.message;}
  else root.querySelector('.message').textContent=result.message;
});
boardsElement.addEventListener('click',event=>{
  const root=event.target.closest('.board');if(!root)return;const board=session.boards[Number(root.dataset.boardIndex)];
  if(event.target.classList.contains('edit-dart')){board.editing={scope:event.target.dataset.scope,index:Number(event.target.dataset.dartIndex)};render();return;}
  if(event.target.classList.contains('cancel-edit')){board.editing=null;render();return;}
  if(!event.target.classList.contains('undo'))return;
  board.editing=null;if(undo(board)){board.lastVisit=null;saveSession();render();}else root.querySelector('.message').textContent='Noch kein Dart zum Korrigieren vorhanden.';
});
document.querySelector('#newSession').addEventListener('click',()=>{if(!confirm('Neue Testsitzung starten? Die aktuellen lokalen Testdaten werden ersetzt.'))return;session=newSession();saveSession();render();});
document.querySelector('#exportSession').addEventListener('click',()=>{const file=new Blob([JSON.stringify(session,null,2)],{type:'application/json'}),link=document.createElement('a');link.href=URL.createObjectURL(file);link.download=`dartvision-test-${new Date().toISOString().slice(0,10)}.json`;link.click();URL.revokeObjectURL(link.href);});
render();
