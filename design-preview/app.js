'use strict';

// Pixel values are unscaled, matching Blender's UI at scale 1.
const presets = {
  reference: { radialColor: '#1b1b1b', extraColor: '#515151', hoverColor: '#6a6a6a', textColor: '#dedede', mutedColor: '#929292', borderColor: '#515151', backgroundColor: '#3b3b3b', radius: 4, fontSize: 13, padding: 9, radialWidth: 144, radialHeight: 35, extraWidth: 186, extraHeight: 24, rowGap: 8, columnGap: 8, horizontalDistance: 200, verticalDistance: 138, diagonalX: 140, diagonalY: 85, blockDistance: 218 },
  prototype: { radialColor: '#090909', extraColor: '#303030', hoverColor: '#525252', textColor: '#dedede', mutedColor: '#787878', borderColor: '#303030', backgroundColor: '#3b3b3b', radius: 4, fontSize: 12, padding: 9, radialWidth: 140, radialHeight: 34, extraWidth: 178, extraHeight: 24, rowGap: 6, columnGap: 8, horizontalDistance: 188, verticalDistance: 137, diagonalX: 137, diagonalY: 85, blockDistance: 202 },
};
const sections = [
  { title: 'Цвета', colors: [['radialColor', 'Круговые кнопки'], ['extraColor', 'Дополнительные кнопки'], ['hoverColor', 'Наведение'], ['hoverTextColor', 'Текст при наведении'], ['textColor', 'Текст'], ['mutedColor', 'Цифры и центр'], ['borderColor', 'Обводка'], ['backgroundColor', 'Фон']] },
  { title: 'Кнопки', ranges: [['radius', 'Скругление', 0, 18], ['fontSize', 'Размер текста', 10, 18], ['padding', 'Отступ текста', 5, 22], ['radialWidth', 'Ширина круговых кнопок', 110, 220], ['radialHeight', 'Высота круговых кнопок', 26, 48], ['extraWidth', 'Ширина дополнительных', 150, 240], ['extraHeight', 'Высота дополнительных', 22, 40]] },
  { title: 'Расположение', ranges: [['horizontalDistance', 'Радиус по горизонтали', 175, 280], ['verticalDistance', 'Радиус по вертикали', 115, 180], ['diagonalX', 'Диагонали по горизонтали', 115, 190], ['diagonalY', 'Диагонали по вертикали', 65, 115], ['blockDistance', 'Расстояние до блоков', 200, 310], ['rowGap', 'Между строками', 2, 16], ['columnGap', 'Между столбцами', 2, 20]] },
];
const storageKey = 'blender-pie-design-v1';
for (const preset of Object.values(presets)) preset.hoverTextColor = '#dedede';
const categories = [
  ['transform', 'Трансформация', '#69bfaf'],
  ['view', 'Вид и отображение', '#83a9d5'],
  ['cursor', 'Курсор и точка опоры', '#d3ae70'],
  ['menu', 'Вложенные меню', '#b49cd4'],
];
function markerDefaults() {
  return { markerMode: 'category', markerSize: 5, buttonColors: {},
    ...Object.fromEntries(categories.map(([key, , color]) => [key + 'Color', color])) };
}
let settings = { ...presets.reference, ...markerDefaults() };
let selectedPreset = 'reference';
let selectedButton = null;
try {
  const stored = localStorage.getItem(storageKey);
  if (stored) { settings = validate(JSON.parse(stored)); selectedPreset = 'custom'; }
} catch { /* Browsers may restrict local storage for local files. */ }

const controls = document.querySelector('#controls');
for (const section of sections) {
  const fieldset = document.createElement('fieldset');
  const legend = document.createElement('legend');
  legend.textContent = section.title;
  fieldset.append(legend);
  for (const [key, title] of section.colors || []) {
    const row = document.createElement('div');
    row.className = 'color-control';
    row.innerHTML = `<label for="${key}">${title}</label><input id="${key}" type="color" data-key="${key}"><input type="text" class="hex" data-key="${key}" aria-label="${title}, HEX" maxlength="7" spellcheck="false" pattern="#[a-fA-F0-9]{6}">`;
    fieldset.append(row);
  }
  for (const [key, title, min, max] of section.ranges || []) {
    const row = document.createElement('div');
    row.className = 'control';
    row.innerHTML = `<div class="control-heading"><label for="${key}">${title}</label><input class="number" type="number" min="${min}" max="${max}" step="1" data-key="${key}" aria-label="${title}, пиксели"></div><input id="${key}" type="range" min="${min}" max="${max}" step="1" data-key="${key}" aria-label="${title}">`;
    fieldset.append(row);
  }
  controls.append(fieldset);
}

const radialItems = [
  ['Frame Selected', '6', 1, 0], ['Rotate', '9', 1, -1],
  ['Move', '8', 0, -1], ['Scale', '7', -1, -1],
  ['Toggle X-Ray', '4', -1, 0], ['Scale', '1', -1, 1],
  ['Modeling ›', '2', 0, 1], ['Rotate', '3', 1, 1],
];
const extraItems = ['Local View', 'Transform Origins', 'Snap Cursor to Selected', 'Cursor to World Origin', 'Pivot to Geometry', 'Pivot to Cursor'];
function categoryFor(caption) {
  if (caption.startsWith('Modeling')) return 'menu';
  if (/Cursor|Pivot/.test(caption)) return 'cursor';
  if (/View|Frame|X-Ray/.test(caption)) return 'view';
  return 'transform';
}
function makeButton(caption, key = '', id) {
  const button = document.createElement('button');
  button.type = 'button';
  button.className = 'pie-button';
  button.title = caption;
  button.dataset.buttonId = id;
  button.dataset.category = categoryFor(caption);
  if (caption === 'Transform Origins') {
    button.setAttribute('aria-pressed', 'false');
    const box = document.createElement('span');
    box.className = 'checkbox';
    box.setAttribute('aria-hidden', 'true');
    button.append(box);
  }
  const text = document.createElement('span');
  text.className = 'caption';
  text.textContent = caption;
  button.append(text);
  if (key) {
    const shortcut = document.createElement('span');
    shortcut.className = 'key';
    shortcut.textContent = key;
    button.append(shortcut);
  }
  button.addEventListener('click', () => {
    document.querySelectorAll('.pie-button.is-selected').forEach(item => item.classList.remove('is-selected'));
    button.classList.add('is-selected');
    selectedButton = button;
    updateMarkerControls();
    if (button.hasAttribute('aria-pressed')) {
      button.setAttribute('aria-pressed', String(button.getAttribute('aria-pressed') !== 'true'));
    }
    document.querySelector('#selection').textContent = `Выбрана кнопка «${caption}»`;
  });
  return button;
}
const radialButtons = radialItems.map(([caption, key], index) => {
  const button = makeButton(caption, key, `radial-${index}`);
  document.querySelector('#radial').append(button);
  return button;
});
for (const block of document.querySelectorAll('.extra-block')) {
  extraItems.forEach((caption, index) => block.append(makeButton(caption, '', `${block.id}-${index}`)));
}

const categoryControls = document.querySelector('#category-colors');
for (const [key, title] of categories) {
  const row = document.createElement('div');
  row.className = 'color-control';
  row.innerHTML = `<label for="category-${key}">${title}</label><input id="category-${key}" type="color" data-category-color="${key}Color"><input type="text" class="hex" data-category-color="${key}Color" aria-label="${title}, цвет метки HEX" maxlength="7" spellcheck="false">`;
  categoryControls.append(row);
}
function buttonMarkerColor(button) {
  const categoryColor = settings[button.dataset.category + 'Color'];
  return settings.markerMode === 'custom'
    ? settings.buttonColors[button.dataset.buttonId] || categoryColor : categoryColor;
}
function updateMarkerControls() {
  document.querySelector('#marker-mode').value = settings.markerMode;
  document.querySelector('#marker-size').value = settings.markerSize;
  document.querySelector('#marker-size-value').textContent = `${settings.markerSize} px`;
  document.querySelector('#marker-size').disabled = settings.markerMode === 'none';
  categoryControls.hidden = settings.markerMode !== 'category';
  document.querySelector('#button-color-control').hidden = settings.markerMode !== 'custom';
  document.querySelectorAll('[data-category-color]').forEach(input => {
    if (document.activeElement !== input) input.value = settings[input.dataset.categoryColor];
  });
  const colorInput = document.querySelector('#button-color');
  colorInput.disabled = !selectedButton;
  document.querySelector('#selected-button-name').textContent = selectedButton
    ? `Цвет для «${selectedButton.title}»` : 'Нажми кнопку в меню, чтобы выбрать её цвет.';
  if (selectedButton) colorInput.value = buttonMarkerColor(selectedButton);
}
document.querySelector('#marker-mode').addEventListener('change', event => {
  settings.markerMode = event.target.value;
  selectedPreset = 'custom';
  render(false);
});
document.querySelector('#marker-size').addEventListener('input', event => {
  settings.markerSize = Number(event.target.value);
  selectedPreset = 'custom';
  render(false);
});
categoryControls.addEventListener('input', event => {
  const input = event.target;
  if (!input.dataset.categoryColor || !/^#[0-9a-f]{6}$/i.test(input.value)) return;
  settings[input.dataset.categoryColor] = input.value.toLowerCase();
  selectedPreset = 'custom';
  render(false);
});
categoryControls.addEventListener('change', updateMarkerControls);
document.querySelector('#button-color').addEventListener('input', event => {
  if (!selectedButton) return;
  settings.buttonColors[selectedButton.dataset.buttonId] = event.target.value;
  selectedPreset = 'custom';
  render(false);
});

function validate(input) {
  if (input?.schemaVersion !== undefined && input.schemaVersion !== 1) throw Error('Неизвестная версия настроек');
  const source = input?.settings ?? input;
  if (!source || typeof source !== 'object' || Array.isArray(source)) throw Error('Некорректный файл настроек');
  const result = {};
  for (const section of sections) {
    for (const [key] of section.colors || []) {
      const color = source[key] ?? (key === 'hoverTextColor' ? '#dedede' : undefined);
      if (!/^#[0-9a-f]{6}$/i.test(color)) throw Error(`Некорректный цвет ${key}`);
      result[key] = color.toLowerCase();
    }
    for (const [key, , min, max] of section.ranges || []) {
      const value = source[key];
      if (typeof value !== 'number' || !Number.isInteger(value) || value < min || value > max) throw Error(`Некорректный размер ${key}`);
      result[key] = value;
    }
  }
  const markers = { ...markerDefaults(), ...source };
  if (!['none', 'category', 'custom'].includes(markers.markerMode)) throw Error('Неизвестный режим меток');
  if (!Number.isInteger(markers.markerSize) || markers.markerSize < 3 || markers.markerSize > 9) throw Error('Некорректный размер метки');
  result.markerMode = markers.markerMode;
  result.markerSize = markers.markerSize;
  for (const [key] of categories) {
    const color = markers[key + 'Color'];
    if (!/^#[0-9a-f]{6}$/i.test(color)) throw Error('Некорректный цвет категории');
    result[key + 'Color'] = color.toLowerCase();
  }
  if (!markers.buttonColors || typeof markers.buttonColors !== 'object' || Array.isArray(markers.buttonColors)) throw Error('Некорректные цвета кнопок');
  result.buttonColors = {};
  for (const [key, color] of Object.entries(markers.buttonColors)) {
    if (!/^(radial-[0-7]|(?:top|bottom)-block-[0-5])$/.test(key) || !/^#[0-9a-f]{6}$/i.test(color)) throw Error('Некорректный цвет кнопки');
    result.buttonColors[key] = color.toLowerCase();
  }
  return result;
}

function render(syncInputs = true) {
  const stage = document.querySelector('#menu-stage');
  for (const [key, value] of Object.entries(settings)) {
    if (typeof value !== 'number' && !key.endsWith('Color')) continue;
    const variable = '--' + key.replace(/[A-Z]/g, letter => '-' + letter.toLowerCase());
    stage.style.setProperty(variable, typeof value === 'number' ? `${value}px` : value);
  }
  stage.dataset.markers = settings.markerMode;
  document.querySelectorAll('.pie-button').forEach(button => {
    button.style.setProperty('--marker-color', buttonMarkerColor(button));
  });
  updateMarkerControls();
  document.querySelector('.preview').style.backgroundColor = settings.backgroundColor;
  radialItems.forEach(([, , x, y], index) => {
    radialButtons[index].style.left = `${x * (y === 0 ? settings.horizontalDistance : settings.diagonalX)}px`;
    radialButtons[index].style.top = `${y * (x === 0 ? settings.verticalDistance : settings.diagonalY)}px`;
  });
  document.querySelector('#top-block').style.top = `-${settings.blockDistance}px`;
  document.querySelector('#bottom-block').style.top = `${settings.blockDistance}px`;
  if (syncInputs) {
    controls.querySelectorAll('[data-key]').forEach(input => { input.value = settings[input.dataset.key]; });
  }
  document.querySelector('#preset').value = selectedPreset;
  resizePreview();
  try { localStorage.setItem(storageKey, JSON.stringify(settings)); } catch { /* Preview also works without storage. */ }
}

controls.addEventListener('input', event => {
  const input = event.target;
  const key = input.dataset.key;
  if (!key) return;
  const color = key.endsWith('Color');
  if (color && !/^#[0-9a-f]{6}$/i.test(input.value)) return;
  if (!color && (!input.validity.valid || input.value === '')) return;
  settings[key] = color ? input.value.toLowerCase() : Number(input.value);
  selectedPreset = 'custom';
  controls.querySelectorAll(`[data-key="${key}"]`).forEach(other => { if (other !== input) other.value = settings[key]; });
  render(false);
});
controls.addEventListener('change', event => {
  const input = event.target;
  if (input.dataset.key) input.value = settings[input.dataset.key];
});
document.querySelector('#preset').addEventListener('change', event => {
  selectedPreset = event.target.value;
  settings = { ...presets[selectedPreset], ...markerDefaults() };
  render();
});
document.querySelector('#reset').addEventListener('click', () => {
  selectedPreset = 'reference';
  settings = { ...presets.reference, ...markerDefaults() };
  render();
});
document.querySelectorAll('[data-background]').forEach(button => {
  button.addEventListener('click', () => {
    document.querySelector('#viewport').classList.toggle('solid', button.dataset.background === 'solid');
    document.querySelectorAll('[data-background]').forEach(item => item.setAttribute('aria-pressed', String(item === button)));
  });
});
function resizePreview() {
  const viewport = document.querySelector('#viewport');
  const width = Math.max(settings.horizontalDistance + settings.radialWidth / 2, settings.diagonalX + settings.radialWidth / 2, settings.extraWidth + settings.columnGap / 2) * 2 + 50;
  const height = Math.max(settings.blockDistance + (settings.extraHeight * 3 + settings.rowGap * 2) / 2, settings.verticalDistance + settings.radialHeight / 2) * 2 + 40;
  const requested = Number(document.querySelector('#zoom').value);
  const scale = Math.min(requested, viewport.clientWidth / width, viewport.clientHeight / height);
  document.querySelector('#menu-stage').style.setProperty('--preview-scale', scale);
  document.querySelector('#actual-scale').textContent = `${Math.round(scale * 100)}%${scale < requested - 0.01 ? ' · по размеру окна' : ''}`;
}
document.querySelector('#zoom').addEventListener('change', resizePreview);
new ResizeObserver(resizePreview).observe(document.querySelector('#viewport'));

let noticeTimer;
function notify(message) {
  const notice = document.querySelector('#notice');
  notice.textContent = message;
  notice.hidden = false;
  clearTimeout(noticeTimer);
  noticeTimer = setTimeout(() => { notice.hidden = true; }, 3500);
}
document.querySelector('#export-json').addEventListener('click', () => {
  const blob = new Blob([JSON.stringify({ schemaVersion: 1, settings }, null, 2) + '\n'], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = 'pie-style.json';
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
});
function pythonStyle() {
  function encode(value) {
    if (typeof value === 'string' && /^#[0-9a-f]{6}$/i.test(value)) {
      return '(' + [1, 3, 5].map(offset => Number((parseInt(value.slice(offset, offset + 2), 16) / 255).toFixed(4))).concat(1.0).join(', ') + ')';
    }
    if (typeof value === 'string') return JSON.stringify(value);
    if (typeof value === 'object') {
      return '{' + Object.entries(value).map(([key, color]) => `${JSON.stringify(key)}: ${encode(color)}`).join(', ') + '}';
    }
    return String(value);
  }
  const lines = ['PIE_STYLE = {'];
  for (const [key, value] of Object.entries(settings)) {
    const name = key.replace(/[A-Z]/g, letter => '_' + letter.toLowerCase());
    const encoded = encode(value);
    lines.push(`    "${name}": ${encoded},`);
  }
  lines.push('}');
  return lines.join('\n');
}
document.querySelector('#copy-python').addEventListener('click', async () => {
  const text = pythonStyle();
  document.querySelector('#python-output').value = text;
  document.querySelector('#export-dialog').showModal();
  document.querySelector('#python-output').select();
  try {
    await navigator.clipboard.writeText(text);
    notify('Параметры Python скопированы');
  } catch { /* The selected text remains available for manual copying. */ }
});
document.querySelector('#import-json').addEventListener('click', () => document.querySelector('#import-file').click());
document.querySelector('#import-file').addEventListener('change', async event => {
  const file = event.target.files[0];
  if (!file) return;
  try {
    settings = validate(JSON.parse(await file.text()));
    selectedPreset = 'custom';
    render();
    notify('Оформление загружено');
  } catch (error) { notify(error.message || 'Не удалось загрузить настройки'); }
  event.target.value = '';
});
render();
