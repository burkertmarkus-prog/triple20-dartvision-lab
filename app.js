const STORAGE_KEY = 'triple20_dartvision_lab_v1';
const BOARD_COUNT = 4;

const startScoreSelect = document.querySelector('#startScore');
const bestOfSelect = document.querySelector('#bestOf');
const boardsElement = document.querySelector('#boards');
const template = document.querySelector('#boardTemplate');

function newBoard(index, startScore = 501, bestOf = 3) {
  return {
    id: index + 1,
    names: { a: '', b: '' },
    remaining: { a: startScore, b: startScore },
    legs: { a: 0, b: 0 },
    active: 'a',
    startScore,
    bestOf,
    winner: null,
    history: []
  };
}

function newSession() {
  const startScore = Number(startScoreSelect.value);
  const bestOf = Number(bestOfSelect.value);
  return {
    createdAt: new Date().toISOString(),
    startScore,
    bestOf,
    boards: Array.from({ length: BOARD_COUNT }, (_, index) => newBoard(index, startScore, bestOf))
  };
}

function loadSession() {
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY));
    if (saved?.boards?.length === BOARD_COUNT) return saved;
  } catch (error) {
    console.warn('Lokale Testdaten konnten nicht gelesen werden.', error);
  }
  return newSession();
}

let session = loadSession();
startScoreSelect.value = String(session.startScore || 501);
bestOfSelect.value = String(session.bestOf || 3);

function saveSession() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
}

function displayName(board, player) {
  return board.names[player].trim() || `Spieler ${player === 'a' ? '1' : '2'}`;
}

function legsNeeded(board) {
  return Math.ceil(board.bestOf / 2);
}

function recordThrow(board, value) {
  if (board.winner) return { ok: false, message: 'Dieses Match ist bereits beendet.' };
  if (!Number.isInteger(value) || value < 0 || value > 180) return { ok: false, message: 'Bitte einen Wert zwischen 0 und 180 eingeben.' };

  board.history.push(JSON.stringify({ remaining: board.remaining, legs: board.legs, active: board.active, winner: board.winner }));
  const player = board.active;
  const next = board.remaining[player] - value;

  if (next < 0 || next === 1) {
    board.active = player === 'a' ? 'b' : 'a';
    return { ok: true, message: 'Bust – Aufnahme wird nicht gewertet.' };
  }

  if (next === 0) {
    board.legs[player] += 1;
    if (board.legs[player] >= legsNeeded(board)) {
      board.remaining[player] = 0;
      board.winner = player;
      return { ok: true, message: `${displayName(board, player)} gewinnt das Match.` };
    }
    board.remaining = { a: board.startScore, b: board.startScore };
    board.active = player === 'a' ? 'b' : 'a';
    return { ok: true, message: `${displayName(board, player)} gewinnt das Leg.` };
  }

  board.remaining[player] = next;
  board.active = player === 'a' ? 'b' : 'a';
  return { ok: true, message: '' };
}

function undo(board) {
  const snapshot = board.history.pop();
  if (!snapshot) return false;
  const previous = JSON.parse(snapshot);
  board.remaining = previous.remaining;
  board.legs = previous.legs;
  board.active = previous.active;
  board.winner = previous.winner;
  return true;
}

function render() {
  boardsElement.replaceChildren();
  session.boards.forEach((board, index) => {
    const fragment = template.content.cloneNode(true);
    const root = fragment.querySelector('.board');
    root.dataset.boardIndex = String(index);
    fragment.querySelector('.board-number').textContent = `BOARD ${board.id}`;
    fragment.querySelector('.board-title').textContent = `Testboard ${board.id}`;
    fragment.querySelector('.player-a-name').value = board.names.a;
    fragment.querySelector('.player-b-name').value = board.names.b;
    fragment.querySelector('.player-a-label').textContent = displayName(board, 'a');
    fragment.querySelector('.player-b-label').textContent = displayName(board, 'b');
    fragment.querySelector('.player-a-score').textContent = board.remaining.a;
    fragment.querySelector('.player-b-score').textContent = board.remaining.b;
    fragment.querySelector('.player-a-legs').textContent = board.legs.a;
    fragment.querySelector('.player-b-legs').textContent = board.legs.b;
    fragment.querySelector('.current-player').textContent = displayName(board, board.active);
    fragment.querySelector(`[data-player="${board.active}"]`).classList.add('active');
    fragment.querySelector(`[data-player="${board.active === 'a' ? 'b' : 'a'}"]`).classList.remove('active');
    const status = fragment.querySelector('.status');
    status.textContent = board.winner ? `${displayName(board, board.winner)} gewinnt` : 'Bereit';
    if (board.winner) status.style.color = 'var(--good)';
    boardsElement.append(fragment);
  });
}

boardsElement.addEventListener('input', event => {
  const root = event.target.closest('.board');
  if (!root || !event.target.classList.contains('player-name')) return;
  const board = session.boards[Number(root.dataset.boardIndex)];
  const player = event.target.classList.contains('player-a-name') ? 'a' : 'b';
  board.names[player] = event.target.value;
  saveSession();
  root.querySelector(`.player-${player}-label`).textContent = displayName(board, player);
  if (board.active === player) root.querySelector('.current-player').textContent = displayName(board, player);
});

boardsElement.addEventListener('submit', event => {
  if (!event.target.classList.contains('throw-form')) return;
  event.preventDefault();
  const root = event.target.closest('.board');
  const board = session.boards[Number(root.dataset.boardIndex)];
  const input = event.target.querySelector('.throw-input');
  const result = recordThrow(board, Number(input.value));
  if (result.ok) {
    saveSession();
    render();
    const updatedRoot = boardsElement.querySelector(`[data-board-index="${root.dataset.boardIndex}"]`);
    updatedRoot.querySelector('.message').textContent = result.message;
    updatedRoot.querySelector('.throw-input').focus();
  } else {
    root.querySelector('.message').textContent = result.message;
  }
});

boardsElement.addEventListener('click', event => {
  if (!event.target.classList.contains('undo')) return;
  const root = event.target.closest('.board');
  const board = session.boards[Number(root.dataset.boardIndex)];
  if (undo(board)) {
    saveSession();
    render();
  } else {
    root.querySelector('.message').textContent = 'Noch keine Eingabe zum Rückgängigmachen vorhanden.';
  }
});

document.querySelector('#newSession').addEventListener('click', () => {
  if (!confirm('Neue Testsitzung starten? Die aktuellen lokalen Testdaten werden ersetzt.')) return;
  session = newSession();
  saveSession();
  render();
});

document.querySelector('#exportSession').addEventListener('click', () => {
  const file = new Blob([JSON.stringify(session, null, 2)], { type: 'application/json' });
  const link = document.createElement('a');
  link.href = URL.createObjectURL(file);
  link.download = `dartvision-test-${new Date().toISOString().slice(0, 10)}.json`;
  link.click();
  URL.revokeObjectURL(link.href);
});

render();
