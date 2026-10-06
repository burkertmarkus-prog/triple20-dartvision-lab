const STORAGE_KEY = 'triple20_dartvision_lab_v2';
const BOARD_COUNT = 4;
const startScoreSelect = document.querySelector('#startScore');
const bestOfSelect = document.querySelector('#bestOf');
const boardsElement = document.querySelector('#boards');
const template = document.querySelector('#boardTemplate');

function newBoard(index, startScore = 501, bestOf = 3) {
  return { id:index+1, names:{a:'',b:''}, remaining:{a:startScore,b:startScore}, legs:{a:0,b:0}, active:'a', visitStart:startScore, currentVisit:[], startScore, bestOf, winner:null, history:[], darts:[] };
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

function recordDart(board,dart){
  if(board.winner)return {ok:false,message:'Dieses Match ist bereits beendet.'};
  board.history.push(snapshot(board));
  const player=board.active, next=board.remaining[player]-dart.score;
  board.currentVisit.push(dart); board.darts.push({...dart,player,at:new Date().toISOString()});
  const invalidCheckout=next===0&&dart.multiplier!==2;
  if(next<0||next===1||invalidCheckout){
    board.remaining[player]=board.visitStart; finishTurn(board);
    return {ok:true,message:invalidCheckout?'Bust – Checkout muss auf einem Doppel erfolgen.':'Bust – Aufnahme wird zurückgesetzt.'};
  }
  board.remaining[player]=next;
  if(next===0){
    board.legs[player]++;
    if(board.legs[player]>=legsNeeded(board)){board.winner=player;board.currentVisit=[];return {ok:true,message:`${displayName(board,player)} gewinnt das Match.`};}
    board.remaining={a:board.startScore,b:board.startScore}; board.active=player==='a'?'b':'a'; board.visitStart=board.startScore; board.currentVisit=[];
    return {ok:true,message:`${displayName(board,player)} gewinnt das Leg.`};
  }
  if(board.currentVisit.length===3)finishTurn(board);
  return {ok:true,message:''};
}
function undo(board){const saved=board.history.pop();if(!saved)return false;Object.assign(board,JSON.parse(saved));return true;}

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
    board.currentVisit.forEach(dart=>{const chip=document.createElement('span');chip.className='dart-chip';chip.textContent=dart.label;darts.append(chip);});
    fragment.querySelector('.visit-total').textContent=`${board.currentVisit.reduce((sum,d)=>sum+d.score,0)} Punkte`;
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
  const result=recordDart(board,createDart(Number(event.target.querySelector('.segment-input').value),Number(event.target.querySelector('.multiplier-input').value)));
  if(result.ok){saveSession();render();boardsElement.querySelector(`[data-board-index="${root.dataset.boardIndex}"] .message`).textContent=result.message;}
  else root.querySelector('.message').textContent=result.message;
});
boardsElement.addEventListener('click',event=>{
  if(!event.target.classList.contains('undo'))return;const root=event.target.closest('.board'),board=session.boards[Number(root.dataset.boardIndex)];
  if(undo(board)){saveSession();render();}else root.querySelector('.message').textContent='Noch kein Dart zum Korrigieren vorhanden.';
});
document.querySelector('#newSession').addEventListener('click',()=>{if(!confirm('Neue Testsitzung starten? Die aktuellen lokalen Testdaten werden ersetzt.'))return;session=newSession();saveSession();render();});
document.querySelector('#exportSession').addEventListener('click',()=>{const file=new Blob([JSON.stringify(session,null,2)],{type:'application/json'}),link=document.createElement('a');link.href=URL.createObjectURL(file);link.download=`dartvision-test-${new Date().toISOString().slice(0,10)}.json`;link.click();URL.revokeObjectURL(link.href);});
render();
