/**
 * Schedule Update Email Builder — STRICT LOCAL-ONLY
 * All CSV parsing and processing runs in the browser. No data is uploaded or sent anywhere.
 * localStorage stores ONLY: column mapping choices and UI settings (no task names, rows, or email body).
 */
(function () {
  'use strict';

  var STORAGE_KEY_MAPPING = 'scheduleEmailBuilder_mapping';
  var STORAGE_KEY_SETTINGS = 'scheduleEmailBuilder_settings';
  var SLACK_LOW_FLOAT_DAYS = 5;

  // ----- Local CSV parser (no external dependency) -----
  function parseCSV(text) {
    var lines = text.split(/\r?\n/).filter(function (l) { return l.length > 0; });
    if (lines.length === 0) return { data: [], meta: { fields: [] } };
    var headers = parseCSVLine(lines[0]);
    var fields = headers;
    var data = [];
    for (var i = 1; i < lines.length; i++) {
      var values = parseCSVLine(lines[i]);
      var row = {};
      for (var j = 0; j < headers.length; j++) {
        row[headers[j]] = values[j] !== undefined ? values[j] : '';
      }
      data.push(row);
    }
    return { data: data, meta: { fields: fields } };
  }

  function parseCSVLine(line) {
    var out = [];
    var i = 0;
    while (i < line.length) {
      if (line[i] === '"') {
        var end = i + 1;
        var s = '';
        while (end < line.length) {
          if (line[end] === '"') {
            if (line[end + 1] === '"') { s += '"'; end += 2; continue; }
            end++;
            break;
          }
          s += line[end++];
        }
        out.push(s);
        i = end;
        while (i < line.length && line[i] !== ',') i++;
        if (line[i] === ',') i++;
        continue;
      }
      var comma = line.indexOf(',', i);
      if (comma === -1) comma = line.length;
      out.push(line.slice(i, comma).replace(/^"|"$/g, '').replace(/""/g, '"'));
      i = comma + 1;
    }
    return out;
  }

  // ----- Column definitions (logical name -> list of header aliases, case-insensitive match) -----
  var COLUMN_DEF = {
    taskName: ['task name', 'name', 'task', 'activity', 'title'],
    start: ['start', 'start date', 'planned start', 'start date'],
    finish: ['finish', 'finish date', 'planned finish', 'finish date'],
    status: ['status', 'status_field', 'task status'],
    actualStart: ['actual start', 'actual start date', 'start (actual)', 'actual_start'],
    actualFinish: ['actual finish', 'actual finish date', 'finish (actual)', 'actual_finish'],
    baselineStart: ['baseline start', 'baseline start date'],
    baselineFinish: ['baseline finish', 'baseline finish date'],
    baseline5Start: ['baseline5 start', 'baseline 5 start'],
    baseline5Finish: ['baseline5 finish', 'baseline 5 finish'],
    totalSlack: ['total slack', 'slack', 'total float'],
    percentComplete: ['% complete', 'percent complete', 'pct complete'],
    duration: ['duration', 'remaining duration', 'duration remaining'],
    wbs: ['wbs', 'outline number', 'outline number'],
    outlineLevel: ['outline level', 'level'],
    resourceNames: ['resource names', 'resources', 'resource'],
    summary: ['summary', 'summary task', 'is summary', 'summary?'],
    milestone: ['milestone', 'milestone?', 'is milestone', 'milestones'],
    taskType: ['task type', 'task_type', 'work type', 'type'],
    completedBy: ['completed by', 'completed_by', 'scheduler', 'scheduler name', 'completed by user'],
  };
  var TEXT_FIELDS = [];
  for (var t = 1; t <= 30; t++) TEXT_FIELDS.push('text' + t);

  function normalizeHeader(h) { return (h || '').trim().toLowerCase(); }

  function autoDetectMapping(csvHeaders) {
    var mapping = {};
    var normalized = {};
    csvHeaders.forEach(function (h) { normalized[normalizeHeader(h)] = h; });
    function mapOne(key, aliases) {
      for (var a = 0; a < aliases.length; a++) {
        if (normalized[aliases[a]]) { mapping[key] = normalized[aliases[a]]; return; }
      }
    }
    Object.keys(COLUMN_DEF).forEach(function (k) { mapOne(k, COLUMN_DEF[k]); });
    TEXT_FIELDS.forEach(function (name) {
      var alias = name.replace(/([a-z])(\d)/, '$1 $2');
      if (normalized[alias] || normalized[name]) mapping[name] = normalized[alias] || normalized[name];
    });
    return mapping;
  }

  function getRequiredMapped(mapping) {
    var ok = mapping.taskName && mapping.start && mapping.finish;
    return { taskName: mapping.taskName, start: mapping.start, finish: mapping.finish, ok: ok };
  }

  // ----- Date parsing (local date only) -----
  function parseDate(s) {
    if (!s || typeof s !== 'string') return null;
    s = s.trim();
    if (!s) return null;
    var rest = s.replace(/^(?:mon|tue|wed|thu|fri|sat|sun)\s+/i, '').trim();
    if (rest) s = rest;
    var d;
    if (/^\d{4}-\d{2}-\d{2}$/.test(s)) {
      d = new Date(s + 'T12:00:00');
    } else if (/^\d{1,2}\/\d{1,2}\/\d{2,4}$/.test(s)) {
      var parts = s.split('/');
      var y = parseInt(parts[2], 10);
      if (y < 100) y += y < 50 ? 2000 : 1900;
      d = new Date(y, parseInt(parts[0], 10) - 1, parseInt(parts[1], 10));
    } else {
      d = new Date(s);
    }
    if (isNaN(d.getTime())) return null;
    return d;
  }

  function dateToYMD(d) {
    if (!d) return '';
    var y = d.getFullYear();
    var m = (d.getMonth() + 1);
    var day = d.getDate();
    return y + '-' + (m < 10 ? '0' : '') + m + '-' + (day < 10 ? '0' : '') + day;
  }

  function formatShortDate(d) {
    if (!d) return '';
    if (typeof d === 'string') {
      var s = d.trim().replace(/^(?:mon|tue|wed|thu|fri|sat|sun)\s+/i, '').trim();
      if (/^\d{4}-\d{2}-\d{2}$/.test(s)) {
        var parts = s.split('-');
        return parseInt(parts[1], 10) + '/' + parseInt(parts[2], 10) + '/' + (parts[0].slice(2));
      }
      if (/^\d{1,2}\/\d{1,2}\/\d{2,4}$/.test(s)) return s.length <= 8 ? s : s.replace(/(\d{1,2})\/(\d{1,2})\/(\d{4})/, function (_, m, d, y) { return m + '/' + d + '/' + y.slice(2); });
      return s;
    }
    var m = d.getMonth() + 1, day = d.getDate(), y = d.getFullYear() % 100;
    return m + '/' + day + '/' + (y < 10 ? '0' : '') + y;
  }

  function dateDays(a, b) {
    if (!a || !b) return 0;
    return Math.round((b.getTime() - a.getTime()) / (24 * 60 * 60 * 1000));
  }

  // ----- Settings (localStorage: only mapping + UI, never task data) -----
  function loadStoredMapping() {
    try {
      var raw = localStorage.getItem(STORAGE_KEY_MAPPING);
      if (raw) return JSON.parse(raw);
    } catch (e) {}
    return null;
  }

  function saveMappingOnly(mapping) {
    try {
      var toStore = {};
      Object.keys(mapping).forEach(function (k) { toStore[k] = mapping[k]; });
      localStorage.setItem(STORAGE_KEY_MAPPING, JSON.stringify(toStore));
    } catch (e) {}
  }

  function loadStoredSettings() {
    try {
      var raw = localStorage.getItem(STORAGE_KEY_SETTINGS);
      if (raw) return JSON.parse(raw);
    } catch (e) {}
    return {};
  }

  function saveSettingsOnly(settings) {
    try {
      localStorage.setItem(STORAGE_KEY_SETTINGS, JSON.stringify(settings));
    } catch (e) {}
  }

  // ----- Get value from row using mapping -----
  function getVal(row, mapping, logicalKey) {
    var header = mapping[logicalKey];
    if (!header) return '';
    var v = row[header];
    return v !== undefined && v !== null ? String(v).trim() : '';
  }

  function getNum(row, mapping, logicalKey) {
    var v = getVal(row, mapping, logicalKey);
    if (!v) return null;
    var n = parseFloat(v.replace(/,/g, ''));
    return isNaN(n) ? null : n;
  }

  // ----- Planned dates (baseline5 -> baseline -> current) -----
  function getPlannedDates(row, mapping, useBaseline) {
    var start = null, finish = null;
    if (useBaseline) {
      if (getVal(row, mapping, 'baseline5Start') && getVal(row, mapping, 'baseline5Finish')) {
        start = parseDate(getVal(row, mapping, 'baseline5Start'));
        finish = parseDate(getVal(row, mapping, 'baseline5Finish'));
      }
      if ((!start || !finish) && getVal(row, mapping, 'baselineStart') && getVal(row, mapping, 'baselineFinish')) {
        start = start || parseDate(getVal(row, mapping, 'baselineStart'));
        finish = finish || parseDate(getVal(row, mapping, 'baselineFinish'));
      }
    }
    if (!start) start = parseDate(getVal(row, mapping, 'start'));
    if (!finish) finish = parseDate(getVal(row, mapping, 'finish'));
    return { start: start, finish: finish };
  }

  function isMilestone(row, mapping) {
    var mv = (getVal(row, mapping, 'milestone') || '').toString().trim().toLowerCase();
    if (/^(yes|true|1|x)$/.test(mv)) return true;
    var dur = getVal(row, mapping, 'duration');
    if (dur !== '' && parseFloat(dur) === 0) return true;
    var name = (getVal(row, mapping, 'taskName') || '').toLowerCase();
    if (name.indexOf('milestone') !== -1) return true;
    return false;
  }

  function isSummary(row, mapping) {
    var sv = getVal(row, mapping, 'summary').toLowerCase();
    if (sv && /^(yes|true|1)$/.test(sv)) return true;
    var level = getNum(row, mapping, 'outlineLevel');
    if (level !== null && level <= 1) return true;
    var wbs = getVal(row, mapping, 'wbs');
    if (wbs && /\.$/.test(wbs)) return true;
    return false;
  }

  function getExpectedStateAndPct(plannedStart, plannedFinish, statusDate) {
    if (!plannedStart || !plannedFinish || !statusDate) return { state: 'Unknown', pct: null };
    var s = statusDate.getTime();
    var startT = plannedStart.getTime();
    var finishT = plannedFinish.getTime();
    if (s < startT) return { state: 'Not started', pct: 0 };
    if (s >= finishT) return { state: 'Finished', pct: 100 };
    var pct = ((s - startT) / (finishT - startT)) * 100;
    pct = Math.max(0, Math.min(100, Math.round(pct * 10) / 10));
    return { state: 'In progress', pct: pct };
  }

  function getFlags(row, mapping, statusDate, useBaseline, threshold) {
    var planned = getPlannedDates(row, mapping, useBaseline);
    var plannedStart = planned.start;
    var plannedFinish = planned.finish;
    var expected = getExpectedStateAndPct(plannedStart, plannedFinish, statusDate);
    var actualStart = parseDate(getVal(row, mapping, 'actualStart'));
    var actualFinish = parseDate(getVal(row, mapping, 'actualFinish'));
    var reportedPct = getNum(row, mapping, 'percentComplete');

    var shouldHaveStarted = false;
    var missingProgress = false;
    var progressDeltaBehind = false;
    var progressDeltaAhead = false;
    var shouldBeFinished = false;

    if (statusDate && plannedStart && statusDate.getTime() >= plannedStart.getTime()) {
      if (!actualStart && (reportedPct === null || reportedPct === 0)) shouldHaveStarted = true;
    }
    if (expected.state === 'In progress' && reportedPct === null) missingProgress = true;
    if (expected.state === 'In progress' && reportedPct !== null && expected.pct !== null) {
      var delta = reportedPct - expected.pct;
      if (delta < -threshold) progressDeltaBehind = true;
      if (delta > threshold) progressDeltaAhead = true;
    }
    if (statusDate && plannedFinish && statusDate.getTime() >= plannedFinish.getTime()) {
      if (!actualFinish || (reportedPct !== null && reportedPct < 100)) shouldBeFinished = true;
    }

    var totalSlackVal = getNum(row, mapping, 'totalSlack');
    var slackHint = '';
    if (totalSlackVal !== null) {
      if (totalSlackVal <= 0) slackHint = '(No float)';
      else if (totalSlackVal <= SLACK_LOW_FLOAT_DAYS) slackHint = '(Low float: ' + totalSlackVal + ' days)';
    }

    return {
      expectedState: expected.state,
      expectedPct: expected.pct,
      reportedPct: reportedPct,
      shouldHaveStarted: shouldHaveStarted,
      missingProgress: missingProgress,
      progressDeltaBehind: progressDeltaBehind,
      progressDeltaAhead: progressDeltaAhead,
      shouldBeFinished: shouldBeFinished,
      slackHint: slackHint,
      plannedStart: plannedStart,
      plannedFinish: plannedFinish,
      actualStart: actualStart,
      actualFinish: actualFinish,
    };
  }

  function isConstructionBoundary(name) {
    var n = name.trim().toLowerCase().replace(/\s+/g, ' ');
    if (/pre.?construction/i.test(n)) return false;
    if (/post.?construction/i.test(n)) return false;
    return /^construction(\s|$)/i.test(n) || n === 'construction';
  }

  function isPostConstructionBoundary(name) {
    var n = name.trim().toLowerCase().replace(/\s+/g, ' ');
    return /^post.?construction/i.test(n);
  }

  function inferPhaseMap(rows, mapping) {
    var constructionStart = null;
    var constructionEnd = null;
    var parentSummary = [];

    for (var i = 0; i < rows.length; i++) {
      var row = rows[i];
      if (!isSummary(row, mapping)) continue;
      var name = getVal(row, mapping, 'taskName');
      if (constructionStart === null && isConstructionBoundary(name)) {
        constructionStart = i;
      } else if (constructionStart !== null && constructionEnd === null && isPostConstructionBoundary(name)) {
        constructionEnd = i;
      }
    }
    if (constructionEnd === null && constructionStart !== null) constructionEnd = rows.length;

    var currentSubPhase = '';
    for (var i = 0; i < rows.length; i++) {
      var phase;
      if (constructionStart !== null && i >= constructionStart && i < constructionEnd) {
        phase = 'construction';
        if (isSummary(rows[i], mapping)) {
          var sn = getVal(rows[i], mapping, 'taskName');
          if (!isConstructionBoundary(sn)) currentSubPhase = sn;
        }
      } else {
        phase = 'preconstructionPost';
        currentSubPhase = '';
      }
      parentSummary.push({ phase: phase, subPhase: currentSubPhase });
    }
    return parentSummary;
  }

  function needsUpdate(flags) {
    return flags.shouldHaveStarted || flags.missingProgress || flags.progressDeltaBehind ||
      flags.progressDeltaAhead || flags.shouldBeFinished;
  }

  function isCompletedByStatus(statusStr) {
    if (!statusStr || typeof statusStr !== 'string') return false;
    var lower = statusStr.trim().toLowerCase();
    return lower === 'complete' || lower === 'completed' || lower === 'done' ||
      lower === 'finished' || lower === 'closed';
  }

  function filterTasksNeedingUpdate(rows, mapping, statusDate, options) {
    var useBaseline = options.useBaseline !== false;
    var threshold = options.threshold != null ? options.threshold : 15;
    var includeMilestones = options.includeMilestones === true;
    var includeSummary = options.includeSummary === true;
    var result = [];
    for (var i = 0; i < rows.length; i++) {
      var row = rows[i];
      if (!includeMilestones && isMilestone(row, mapping)) continue;
      if (!includeSummary && isSummary(row, mapping)) continue;
      var actualFinishDate = parseDate(getVal(row, mapping, 'actualFinish'));
      if (actualFinishDate) continue;
      if (isCompletedByStatus(getVal(row, mapping, 'status'))) continue;
      var flags = getFlags(row, mapping, statusDate, useBaseline, threshold);
      if (!needsUpdate(flags)) continue;
      var groupValue = '';
      if (options.groupBy) groupValue = getVal(row, mapping, options.groupBy);
      result.push({
        row: row,
        rowIndex: i,
        mapping: mapping,
        flags: flags,
        groupValue: groupValue,
        taskName: getVal(row, mapping, 'taskName'),
        status: getVal(row, mapping, 'status'),
        start: getVal(row, mapping, 'start'),
        finish: getVal(row, mapping, 'finish'),
        actualStart: getVal(row, mapping, 'actualStart'),
        actualFinish: getVal(row, mapping, 'actualFinish'),
        baselineStart: getVal(row, mapping, 'baselineStart'),
        baselineFinish: getVal(row, mapping, 'baselineFinish'),
        baseline5Start: getVal(row, mapping, 'baseline5Start'),
        baseline5Finish: getVal(row, mapping, 'baseline5Finish'),
        totalSlack: getVal(row, mapping, 'totalSlack'),
        taskType: getVal(row, mapping, 'taskType'),
        completedBy: getVal(row, mapping, 'completedBy'),
        expectedState: flags.expectedState,
        expectedPct: flags.expectedPct,
        reportedPct: flags.reportedPct,
      });
    }
    return result;
  }

  function generateQuestion(task, statusDateStr) {
    var f = task.flags;
    var plannedStartStr = task.plannedStartStr || '';
    var plannedFinishStr = task.plannedFinishStr || '';
    var hasActualStart = !!f.actualStart;
    var isOneDayTask = f.plannedStart && f.plannedFinish &&
      dateToYMD(f.plannedStart) === dateToYMD(f.plannedFinish);

    if (hasActualStart) {
      if (f.shouldBeFinished)
        return 'Complete? If yes, what was the actual finish date? If not, current % and forecast finish?';
      return 'Current % complete? Still on track for ' + plannedFinishStr + '?';
    }

    if (f.shouldHaveStarted)
      return 'Started yet? If yes, actual start and % complete. If not, when will it start and what will be the new start and finish dates?';
    if (f.shouldBeFinished)
      return 'Complete? If yes, what was the actual finish date? If not, current % and forecast finish?';
    if (f.missingProgress || f.progressDeltaBehind || f.progressDeltaAhead)
      return 'Current % complete? Still on track for ' + plannedFinishStr + '?';
    return 'Quick confirm: status and % complete as of ' + statusDateStr + '.';
  }

  function renderTaskBlock(lines, t, statusDateStr, index) {
    var label = t.taskName;
    if (t.constructionSubPhase) label = t.constructionSubPhase + ' – ' + label;
    if (t.taskType) label = label + ' (' + t.taskType + ')';
    var plannedStart = formatShortDate(t.flags.plannedStart) || t.start;
    var plannedFinish = formatShortDate(t.flags.plannedFinish) || t.finish;
    var actualStr = (t.actualStart || t.actualFinish) ? ((t.actualStart || 'None') + '-' + (t.actualFinish || 'None')) : 'None-None';
    var part = (index != null ? index + '. ' : '') + label + ': Planned ' + plannedStart + '-' + plannedFinish + '; Actual ' + actualStr + '. ' + generateQuestion(t, statusDateStr);
    if (t.completedBy) part += ' (Completed by: ' + t.completedBy + ')';
    lines.push(part);
  }

  function formatEmailBody(needsUpdateList, statusDateStr, deadline, groupBy) {
    var lines = [];
    lines.push('Team,');
    lines.push('');
    lines.push('Please provide a status update on the following tasks. PMs & PEs please see 1st section. Superintendents & PMs please see 2nd section. Please provide actual start/finish & % complete (or confirm no change). Please reply by ' + (deadline || 'EOD tomorrow') + '.');
    lines.push('');

    if (needsUpdateList.length === 0) {
      lines.push('Nothing needs an update for this date.');
      return lines.join('\n');
    }

    var hasPhase = needsUpdateList.some(function (t) { return t.phaseCategory === 'construction'; });

    if (!hasPhase) {
      needsUpdateList.forEach(function (t, i) { renderTaskBlock(lines, t, statusDateStr, i + 1); });
      lines.push('Thank you,');
      lines.push('Scheduling & Data Analytics');
      return lines.join('\n');
    }

    var prePost = needsUpdateList.filter(function (t) { return t.phaseCategory !== 'construction'; });
    var construction = needsUpdateList.filter(function (t) { return t.phaseCategory === 'construction'; });

    if (prePost.length > 0) {
      lines.push('Preconstruction & post');
      prePost.forEach(function (t, i) { renderTaskBlock(lines, t, statusDateStr, i + 1); });
    }

    if (construction.length > 0) {
      if (prePost.length > 0) lines.push('');
      lines.push('Construction');
      construction.forEach(function (t, i) { renderTaskBlock(lines, t, statusDateStr, i + 1); });
    }

    lines.push('Thank you,');
    lines.push('Scheduling & Data Analytics');
    return lines.join('\n');
  }

  function escapeCsvCell(s) {
    if (s == null) s = '';
    s = String(s);
    if (/[",\r\n]/.test(s)) return '"' + s.replace(/"/g, '""') + '"';
    return s;
  }

  function phaseCategoryLabel(t) {
    if (t.phaseCategory === 'construction') return 'Construction';
    return 'Preconstruction & Post Construction';
  }

  function exportNeedsUpdateCSV(needsUpdateList, statusDateStr) {
    var headers = ['Task Name', 'Phase', 'Status', 'Start', 'Finish', 'Actual Start', 'Actual Finish', 'Baseline Start', 'Baseline Finish', 'Baseline5 Start', 'Baseline5 Finish', 'Total Slack', 'Expected State', 'Expected %', 'Reported %', 'Question'];
    var rows = needsUpdateList.map(function (t) {
      var q = generateQuestion(t, statusDateStr);
      return [
        t.taskName,
        phaseCategoryLabel(t),
        t.status,
        t.start,
        t.finish,
        t.actualStart,
        t.actualFinish,
        t.baselineStart,
        t.baselineFinish,
        t.baseline5Start,
        t.baseline5Finish,
        t.totalSlack,
        t.expectedState,
        t.expectedPct != null ? t.expectedPct : '',
        t.reportedPct != null ? t.reportedPct : '',
        q,
      ];
    });
    var csv = [headers.map(escapeCsvCell).join(',')].concat(rows.map(function (r) { return r.map(escapeCsvCell).join(','); })).join('\r\n');
    return csv;
  }

  // ----- In-memory state (never persisted) -----
  var state = {
    rawRows: null,
    csvHeaders: null,
    mapping: null,
    needsUpdateList: null,
    statusDateStr: null,
    deadline: null,
    groupBy: null,
  };

  function clearSession(keepMapping) {
    state.rawRows = null;
    state.csvHeaders = null;
    if (!keepMapping) state.mapping = null;
    state.needsUpdateList = null;
    state.statusDateStr = null;
    state.deadline = null;
    state.groupBy = null;
    var out = document.getElementById('schedule-email-output');
    var card = document.getElementById('schedule-email-output-card');
    if (out) out.value = '';
    if (card) card.style.display = 'none';
    var copyFeedback = document.getElementById('schedule-email-copy-feedback');
    if (copyFeedback) copyFeedback.textContent = '';
  }

  function getSettings() {
    var stored = loadStoredSettings();
    return {
      useBaseline: document.getElementById('schedule-email-use-baseline').checked,
      threshold: parseInt(document.getElementById('schedule-email-threshold').value, 10) || 15,
      includeMilestones: document.getElementById('schedule-email-include-milestones').checked,
      includeSummary: document.getElementById('schedule-email-include-summary').checked,
      groupBy: (document.getElementById('schedule-email-group-by').value || '').trim() || null,
      deadline: (document.getElementById('schedule-email-deadline').value || 'by EOD tomorrow').trim(),
      saved: stored,
    };
  }

  function applyStoredSettings() {
    var s = loadStoredSettings();
    if (s.threshold != null) document.getElementById('schedule-email-threshold').value = s.threshold;
    if (s.useBaseline !== undefined) document.getElementById('schedule-email-use-baseline').checked = s.useBaseline;
    if (s.includeMilestones !== undefined) document.getElementById('schedule-email-include-milestones').checked = s.includeMilestones;
    if (s.includeSummary !== undefined) document.getElementById('schedule-email-include-summary').checked = s.includeSummary;
    if (s.deadline !== undefined) document.getElementById('schedule-email-deadline').value = s.deadline;
  }

  function runGenerate() {
    var statusDateEl = document.getElementById('schedule-email-status-date');
    var statusDateStr = statusDateEl ? statusDateEl.value : '';
    if (!statusDateStr) {
      alert('Please set the status date.');
      return;
    }
    if (!state.rawRows || !state.mapping) {
      alert('Please upload a CSV and ensure required columns are mapped.');
      return;
    }
    var req = getRequiredMapped(state.mapping);
    if (!req.ok) {
      alert('Please map Task Name, Start, and Finish in the column mapping section.');
      return;
    }

    var statusDate = parseDate(statusDateStr);
    if (!statusDate) {
      alert('Invalid status date.');
      return;
    }

    var settings = getSettings();
    var options = {
      useBaseline: settings.useBaseline,
      threshold: settings.threshold,
      includeMilestones: settings.includeMilestones,
      includeSummary: settings.includeSummary,
      groupBy: settings.groupBy,
    };
    saveSettingsOnly({
      threshold: settings.threshold,
      useBaseline: settings.useBaseline,
      includeMilestones: settings.includeMilestones,
      includeSummary: settings.includeSummary,
      deadline: settings.deadline,
      groupBy: settings.groupBy,
    });

    var list = filterTasksNeedingUpdate(state.rawRows, state.mapping, statusDate, options);
    var phaseMap = inferPhaseMap(state.rawRows, state.mapping);
    list.forEach(function (t) {
      t.plannedStartStr = t.flags.plannedStart ? dateToYMD(t.flags.plannedStart) : '';
      t.plannedFinishStr = t.flags.plannedFinish ? dateToYMD(t.flags.plannedFinish) : '';
      var pm = phaseMap[t.rowIndex];
      t.phaseCategory = pm ? pm.phase : 'preconstructionPost';
      t.constructionSubPhase = pm ? pm.subPhase : '';
    });
    state.needsUpdateList = list;
    state.statusDateStr = statusDateStr;
    state.deadline = settings.deadline;
    state.groupBy = settings.groupBy;

    var body = formatEmailBody(list, statusDateStr, settings.deadline, options.groupBy);
    var out = document.getElementById('schedule-email-output');
    var card = document.getElementById('schedule-email-output-card');
    if (out) out.value = body;
    if (card) card.style.display = 'block';
  }

  function buildMappingUI(csvHeaders, currentMapping) {
    var section = document.getElementById('schedule-email-mapping-section');
    var fieldsEl = document.getElementById('schedule-email-mapping-fields');
    var previewEl = document.getElementById('schedule-email-preview');
    if (!section || !fieldsEl || !previewEl) return;

    var required = [
      { key: 'taskName', label: 'Task Name' },
      { key: 'start', label: 'Start' },
      { key: 'finish', label: 'Finish' },
    ];
    var html = '<table><thead><tr><th>Logical field</th><th>CSV column</th></tr></thead><tbody>';
    required.forEach(function (r) {
      html += '<tr><td><label for="map-' + r.key + '">' + r.label + '</label></td><td><select id="map-' + r.key + '">';
      html += '<option value="">-- Select --</option>';
      csvHeaders.forEach(function (h) {
        var sel = (currentMapping[r.key] === h) ? ' selected' : '';
        html += '<option value="' + escapeHtml(h) + '"' + sel + '>' + escapeHtml(h) + '</option>';
      });
      html += '</select></td></tr>';
    });
    html += '</tbody></table>';
    fieldsEl.innerHTML = html;

    var maxPreview = 20;
    var previewRows = (state.rawRows || []).slice(0, maxPreview);
    var mappedHeaders = [currentMapping.taskName, currentMapping.start, currentMapping.finish].filter(Boolean);
    if (mappedHeaders.length === 0) mappedHeaders = csvHeaders.slice(0, 3);
    var previewHtml = '<table class="schedule-email-preview-table"><thead><tr>';
    mappedHeaders.forEach(function (h) { previewHtml += '<th>' + escapeHtml(h) + '</th>'; });
    previewHtml += '</tr></thead><tbody>';
    previewRows.forEach(function (row) {
      previewHtml += '<tr>';
      mappedHeaders.forEach(function (h) { previewHtml += '<td>' + escapeHtml(row[h] || '') + '</td>'; });
      previewHtml += '</tr>';
    });
    previewHtml += '</table>';
    previewEl.innerHTML = previewHtml;
  }

  function escapeHtml(s) {
    if (s == null) return '';
    var div = document.createElement('div');
    div.textContent = s;
    return div.innerHTML;
  }

  function populateGroupBy(mapping) {
    var sel = document.getElementById('schedule-email-group-by');
    if (!sel) return;
    var opts = [{ value: '', text: 'None' }];
    var optionalKeys = ['resourceNames', 'wbs'].concat(TEXT_FIELDS);
    optionalKeys.forEach(function (k) {
      if (mapping[k]) opts.push({ value: k, text: k + ' (' + mapping[k] + ')' });
    });
    sel.innerHTML = opts.map(function (o) { return '<option value="' + escapeHtml(o.value) + '">' + escapeHtml(o.text) + '</option>'; }).join('');
    var stored = loadStoredSettings();
    if (stored.groupBy && opts.some(function (o) { return o.value === stored.groupBy; })) {
      sel.value = stored.groupBy;
    }
  }

  function onFileSelected(e) {
    var file = e.target && e.target.files && e.target.files[0];
    if (!file) return;
    var reader = new FileReader();
    reader.onload = function (ev) {
      var text = ev.target && ev.target.result;
      if (typeof text !== 'string') return;
      var parsed = parseCSV(text);
      state.rawRows = parsed.data;
      state.csvHeaders = parsed.meta.fields || [];
      var mapping = autoDetectMapping(state.csvHeaders);
      var stored = loadStoredMapping();
      if (stored && typeof stored === 'object') {
        var valid = {};
        state.csvHeaders.forEach(function (h) {
          Object.keys(stored).forEach(function (k) {
            if (stored[k] === h) valid[k] = h;
          });
        });
        if (valid.taskName && valid.start && valid.finish) {
          mapping = Object.assign({}, mapping, valid);
        }
      }
      state.mapping = mapping;
      var req = getRequiredMapped(mapping);
      var section = document.getElementById('schedule-email-mapping-section');
      if (!req.ok && section) {
        section.style.display = 'block';
        buildMappingUI(state.csvHeaders, mapping);
      } else if (section) {
        section.style.display = 'none';
      }
      populateGroupBy(mapping);
      var out = document.getElementById('schedule-email-output');
      var card = document.getElementById('schedule-email-output-card');
      if (out) out.value = '';
      if (card) card.style.display = 'none';
    };
    reader.readAsText(file, 'UTF-8');
  }

  function onApplyMapping() {
    var mapping = state.mapping || {};
    mapping.taskName = document.getElementById('map-taskName') && document.getElementById('map-taskName').value;
    mapping.start = document.getElementById('map-start') && document.getElementById('map-start').value;
    mapping.finish = document.getElementById('map-finish') && document.getElementById('map-finish').value;
    state.mapping = mapping;
    saveMappingOnly(mapping);
    var req = getRequiredMapped(mapping);
    if (req.ok) {
      document.getElementById('schedule-email-mapping-section').style.display = 'none';
      populateGroupBy(mapping);
    }
    buildMappingUI(state.csvHeaders, mapping);
  }

  function init() {
    applyStoredSettings();
    var statusDateEl = document.getElementById('schedule-email-status-date');
    if (statusDateEl && !statusDateEl.value) {
      var today = new Date();
      statusDateEl.value = dateToYMD(today);
    }
    var csvInput = document.getElementById('schedule-email-csv');
    if (csvInput) csvInput.addEventListener('change', onFileSelected);

    document.getElementById('schedule-email-generate').addEventListener('click', runGenerate);

    document.getElementById('schedule-email-clear').addEventListener('click', function () {
      clearSession(true);
    });

    document.getElementById('schedule-email-copy').addEventListener('click', function () {
      var ta = document.getElementById('schedule-email-output');
      var feedback = document.getElementById('schedule-email-copy-feedback');
      if (!ta || !ta.value) return;
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(ta.value).then(function () {
          if (feedback) feedback.textContent = 'Copied to clipboard.';
        }).catch(function () {
          if (feedback) feedback.textContent = 'Copy failed.';
        });
      } else {
        if (feedback) feedback.textContent = 'Clipboard not available.';
      }
    });

    document.getElementById('schedule-email-export-csv').addEventListener('click', function () {
      if (!state.needsUpdateList || state.needsUpdateList.length === 0) {
        alert('Generate the email body first.');
        return;
      }
      var csv = exportNeedsUpdateCSV(state.needsUpdateList, state.statusDateStr);
      var blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
      var a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = 'schedule_needs_update_' + (state.statusDateStr || 'export') + '.csv';
      a.click();
      URL.revokeObjectURL(a.href);
    });

    var applyBtn = document.getElementById('schedule-email-apply-mapping');
    if (applyBtn) applyBtn.addEventListener('click', onApplyMapping);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  // Expose for JS unit tests when test runner is present (local-only; never in production requests)
  if (typeof document !== 'undefined' && document.getElementById('schedule-email-builder-test-runner')) {
    window._scheduleEmailBuilderTest = {
      parseDate: parseDate,
      dateToYMD: dateToYMD,
      getExpectedStateAndPct: getExpectedStateAndPct,
      getFlags: getFlags,
      needsUpdate: needsUpdate,
      generateQuestion: generateQuestion,
    };
  }
})();
