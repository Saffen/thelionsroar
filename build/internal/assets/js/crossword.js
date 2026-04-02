(function () {
  function safeParse(text) {
    try {
      return JSON.parse(text);
    } catch (error) {
      console.error('Failed to parse crossword data.', error);
      return null;
    }
  }

  function keyFor(row, col) {
    return `${row}-${col}`;
  }

  function loadStoredGuesses(storageKey) {
    try {
      const raw = window.localStorage.getItem(storageKey);
      if (!raw) return {};
      const parsed = JSON.parse(raw);
      return parsed && typeof parsed === 'object' ? parsed : {};
    } catch (error) {
      console.error('Failed to restore crossword progress.', error);
      return {};
    }
  }

  document.addEventListener('DOMContentLoaded', function () {
    const dataElement = document.getElementById('crossword-data');
    const root = document.querySelector('[data-crossword-root]');
    if (!dataElement || !root) return;

    const puzzle = safeParse(dataElement.textContent || '{}');
    if (!puzzle) return;

    const gridElement = root.querySelector('.crossword-grid');
    const acrossList = root.querySelector('[data-clues="across"]');
    const downList = root.querySelector('[data-clues="down"]');
    const statusElement = root.querySelector('.crossword-status');
    const activeClueElement = root.querySelector('.crossword-active-clue');
    if (!gridElement || !acrossList || !downList || !statusElement || !activeClueElement) return;

    const storageKey = `lr-crossword:${puzzle.id}`;
    const guesses = loadStoredGuesses(storageKey);
    const cellButtons = new Map();
    const clueButtons = new Map();
    const cellsByKey = new Map();
    const words = puzzle.words || {};
    const clueGroups = puzzle.clues || { across: [], down: [] };
    const allClues = clueGroups.across.concat(clueGroups.down);

    puzzle.cells.forEach(function (rowCells) {
      rowCells.forEach(function (cell) {
        if (cell) {
          cellsByKey.set(keyFor(cell.row, cell.col), cell);
        }
      });
    });

    let selectedKey = allClues.length ? keyFor(allClues[0].row, allClues[0].col) : null;
    let activeDirection = 'across';

    function saveGuesses() {
      try {
        window.localStorage.setItem(storageKey, JSON.stringify(guesses));
      } catch (error) {
        console.error('Failed to save crossword progress.', error);
      }
    }

    function clueIdForCell(cell, preferredDirection) {
      if (!cell) return null;
      const primary = preferredDirection === 'down' ? cell.down_id : cell.across_id;
      if (primary) return primary;
      return preferredDirection === 'down' ? cell.across_id : cell.down_id;
    }

    function getSelectedCell() {
      return selectedKey ? cellsByKey.get(selectedKey) || null : null;
    }

    function getActiveClue() {
      const cell = getSelectedCell();
      const clueId = clueIdForCell(cell, activeDirection);
      return clueId ? words[clueId] || null : null;
    }

    function renderGrid() {
      gridElement.style.gridTemplateColumns = `repeat(${puzzle.cols}, minmax(0, 1fr))`;
      gridElement.innerHTML = '';

      puzzle.cells.forEach(function (rowCells) {
        rowCells.forEach(function (cell) {
          if (!cell) {
            const block = document.createElement('div');
            block.className = 'crossword-block';
            gridElement.appendChild(block);
            return;
          }

          const button = document.createElement('button');
          button.type = 'button';
          button.className = 'crossword-cell';
          button.dataset.cellKey = keyFor(cell.row, cell.col);
          button.setAttribute('role', 'gridcell');
          button.setAttribute('aria-label', `Row ${cell.row + 1}, column ${cell.col + 1}`);

          if (cell.number) {
            const number = document.createElement('span');
            number.className = 'crossword-cell-number';
            number.textContent = String(cell.number);
            button.appendChild(number);
          }

          const letter = document.createElement('span');
          letter.className = 'crossword-cell-letter';
          letter.textContent = guesses[button.dataset.cellKey] || '';
          button.appendChild(letter);

          cellButtons.set(button.dataset.cellKey, button);
          gridElement.appendChild(button);
        });
      });
    }

    function renderClues(listElement, direction) {
      listElement.innerHTML = '';
      clueGroups[direction].forEach(function (clue) {
        const item = document.createElement('li');
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'crossword-clue-button';
        button.dataset.clueId = clue.id;

        const label = document.createElement('span');
        label.innerHTML = `<span class="crossword-clue-number">${clue.number}</span>${clue.clue}`;
        button.appendChild(label);

        const length = document.createElement('span');
        length.className = 'crossword-clue-length';
        length.textContent = `${clue.answer_length} letters`;
        button.appendChild(length);

        clueButtons.set(clue.id, button);
        item.appendChild(button);
        listElement.appendChild(item);
      });
    }

    function setSelectedCell(nextKey, nextDirection) {
      if (!nextKey || !cellsByKey.has(nextKey)) return;
      selectedKey = nextKey;
      activeDirection = nextDirection || activeDirection;

      const cell = getSelectedCell();
      if (cell && !clueIdForCell(cell, activeDirection)) {
        activeDirection = cell.across_id ? 'across' : 'down';
      }

      updateHighlights();
    }

    function moveWithinClue(step) {
      const activeClue = getActiveClue();
      if (!activeClue) return;
      const index = activeClue.cells.indexOf(selectedKey);
      const nextKey = activeClue.cells[index + step];
      if (nextKey) {
        setSelectedCell(nextKey, activeDirection);
      }
    }

    function moveAbsolute(rowDelta, colDelta, nextDirection) {
      const cell = getSelectedCell();
      if (!cell) return;
      const nextKey = keyFor(cell.row + rowDelta, cell.col + colDelta);
      if (cellsByKey.has(nextKey)) {
        setSelectedCell(nextKey, nextDirection);
      }
    }

    function updateStatus(message) {
      const total = cellsByKey.size;
      let filled = 0;
      let correct = 0;

      cellsByKey.forEach(function (cell, key) {
        const guess = guesses[key] || '';
        if (guess) filled += 1;
        if (guess === cell.solution) correct += 1;
      });

      const solved = total > 0 && correct === total;
      statusElement.textContent = message || (solved ? 'Puzzle solved. Progress saved on this device.' : `${filled} of ${total} squares filled`);
      statusElement.classList.toggle('is-solved', solved);

      const activeClue = getActiveClue();
      activeClueElement.textContent = activeClue ? `${activeClue.number} ${activeClue.direction}: ${activeClue.clue}` : '';
    }

    function updateHighlights() {
      const activeClue = getActiveClue();
      const activeCells = new Set(activeClue ? activeClue.cells : []);

      cellButtons.forEach(function (button, key) {
        const letter = button.querySelector('.crossword-cell-letter');
        const cell = cellsByKey.get(key);
        const guess = guesses[key] || '';

        if (letter) {
          letter.textContent = guess;
        }

        button.classList.toggle('is-selected', key === selectedKey);
        button.classList.toggle('is-active', activeCells.has(key));
        button.classList.toggle('is-correct', Boolean(guess) && guess === cell.solution);
      });

      clueButtons.forEach(function (button, clueId) {
        button.classList.toggle('is-active', Boolean(activeClue) && activeClue.id === clueId);
      });

      updateStatus();
    }

    function writeLetter(letter) {
      if (!selectedKey) return;
      guesses[selectedKey] = letter.toUpperCase();
      saveGuesses();
      moveWithinClue(1);
      updateHighlights();
    }

    function clearCurrentCell(moveBackward) {
      if (!selectedKey) return;
      if (guesses[selectedKey]) {
        delete guesses[selectedKey];
      } else if (moveBackward) {
        moveWithinClue(-1);
        if (selectedKey && guesses[selectedKey]) {
          delete guesses[selectedKey];
        }
      }
      saveGuesses();
      updateHighlights();
    }

    function toggleDirection() {
      const cell = getSelectedCell();
      if (!cell || !cell.across_id || !cell.down_id) return;
      activeDirection = activeDirection === 'across' ? 'down' : 'across';
      updateHighlights();
    }

    function clearPuzzle() {
      Object.keys(guesses).forEach(function (key) {
        delete guesses[key];
      });
      saveGuesses();
      updateHighlights();
    }

    renderGrid();
    renderClues(acrossList, 'across');
    renderClues(downList, 'down');

    if (selectedKey && !cellsByKey.has(selectedKey)) {
      selectedKey = cellsByKey.size ? Array.from(cellsByKey.keys())[0] : null;
    }

    updateHighlights();

    gridElement.addEventListener('click', function (event) {
      const button = event.target.closest('[data-cell-key]');
      if (!button) return;
      const nextKey = button.dataset.cellKey;
      const cell = cellsByKey.get(nextKey);
      if (!cell) return;

      if (selectedKey === nextKey && cell.across_id && cell.down_id) {
        toggleDirection();
        return;
      }

      const nextDirection = clueIdForCell(cell, activeDirection) ? activeDirection : (cell.across_id ? 'across' : 'down');
      setSelectedCell(nextKey, nextDirection);
    });

    root.addEventListener('click', function (event) {
      const actionButton = event.target.closest('[data-action]');
      if (actionButton) {
        const action = actionButton.dataset.action;
        if (action === 'toggle-direction') toggleDirection();
        if (action === 'clear-cell') clearCurrentCell(false);
        if (action === 'clear-puzzle') clearPuzzle();
        return;
      }

      const clueButton = event.target.closest('[data-clue-id]');
      if (!clueButton) return;
      const clue = words[clueButton.dataset.clueId];
      if (!clue) return;
      setSelectedCell(keyFor(clue.row, clue.col), clue.direction);
    });

    document.addEventListener('keydown', function (event) {
      const tagName = event.target && event.target.tagName ? event.target.tagName.toLowerCase() : '';
      if (tagName === 'input' || tagName === 'textarea' || tagName === 'select' || event.target.isContentEditable) {
        return;
      }

      if (!selectedKey) return;

      if (/^[a-z0-9]$/i.test(event.key)) {
        event.preventDefault();
        writeLetter(event.key);
        return;
      }

      if (event.key === 'Backspace') {
        event.preventDefault();
        clearCurrentCell(true);
        return;
      }

      if (event.key === 'Delete') {
        event.preventDefault();
        clearCurrentCell(false);
        return;
      }

      if (event.key === 'Tab' || event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        toggleDirection();
        return;
      }

      if (event.key === 'ArrowLeft') {
        event.preventDefault();
        moveAbsolute(0, -1, 'across');
        return;
      }

      if (event.key === 'ArrowRight') {
        event.preventDefault();
        moveAbsolute(0, 1, 'across');
        return;
      }

      if (event.key === 'ArrowUp') {
        event.preventDefault();
        moveAbsolute(-1, 0, 'down');
        return;
      }

      if (event.key === 'ArrowDown') {
        event.preventDefault();
        moveAbsolute(1, 0, 'down');
      }
    });
  });
})();
