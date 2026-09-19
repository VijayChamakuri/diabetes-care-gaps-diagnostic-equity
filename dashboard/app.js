/* Dashboard UI. Every number comes from window.DATA, which is built from outputs/tables. */
(function () {
  "use strict";
  var D = window.DATA;
  var theme = new URLSearchParams(location.search).get("theme");
  if (theme === "light" || theme === "dark") document.documentElement.setAttribute("data-theme", theme);
  var GROUPS = D.meta.groups, ALL = "All groups";
  var TABS = [["overview", "Care Gap Overview"], ["models", "Model Tradeoffs"], ["methods", "Methods & Data Quality"]];
  var MODEL_NAMES = {};
  D.model_specification.forEach(function (m) { MODEL_NAMES[m.model] = m.description + " (" + m.role + ")"; });
  var state = { tab: "overview", model: "demographic_logistic", metric: "sensitivity", hidden: {}, hideSmall: false,
    standardized: false, interval: "logit", missingVar: "bmi" };

  function esc(v) { return String(v === null || v === undefined ? "" : v).replace(/[&<>"']/g, function (c) {
    return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  function pct(x, d) { return x === null || x === undefined || isNaN(x) ? "n/a" : (x * 100).toFixed(d === undefined ? 1 : d) + "%"; }
  function pp(x) { return (x >= 0 ? "+" : "") + (x * 100).toFixed(1) + " pp"; }
  function num(x) { return Number(x).toLocaleString("en-US"); }
  function mil(x) { return (x / 1e6).toFixed(1) + " million"; }
  function pval(p) { return p < 0.001 ? "p < 0.001" : "p = " + p.toFixed(3); }
  function byGroup(rows) { var o = {}; rows.forEach(function (r) { o[r.group] = r; }); return o; }
  function card(label, value, sub) { return '<div class="card"><div class="card-label">' + label + '</div><div class="card-value">' + value + '</div><div class="card-sub">' + sub + "</div></div>"; }
  function table(headers, rows, numeric) {
    numeric = numeric || [];
    return '<div class="table-wrap"><table><thead><tr>' + headers.map(function (h, i) { return "<th" + (numeric.indexOf(i) >= 0 ? ' class="num"' : "") + ' scope="col">' + esc(h) + "</th>"; }).join("") +
      "</tr></thead><tbody>" + rows.map(function (r) { return "<tr>" + r.map(function (c, i) { return "<td" + (numeric.indexOf(i) >= 0 ? ' class="num"' : "") + ">" + c + "</td>"; }).join("") + "</tr>"; }).join("") + "</tbody></table></div>";
  }
  function flag(text) { return ' <span class="flag">' + esc(text) + "</span>"; }

  /* ---------- svg helpers ---------- */
  function scale(d0, d1, r0, r1) { return function (v) { return r0 + (v - d0) * (r1 - r0) / (d1 - d0); }; }
  function svg(w, h, label, inner) { return '<svg viewBox="0 0 ' + w + " " + h + '" role="img" aria-label="' + esc(label) + '" class="chart">' + inner + "</svg>"; }

  /* rows: [{label, series:[{est, lo, hi, color, shape, hollow, note}]}] */
  function dotChart(rows, opts) {
    var W = 760, L = 150, R = opts.rightPad || 265, T = 16, rowH = opts.rowH || 44, B = 40, H = T + rows.length * rowH + B;
    var x = scale(opts.min, opts.max, L, W - R), inner = "";
    (opts.ticks || []).forEach(function (t) { inner += '<line x1="' + x(t) + '" x2="' + x(t) + '" y1="' + T + '" y2="' + (H - B) + '" class="grid"/><text x="' + x(t) + '" y="' + (H - B + 16) + '" class="axis" text-anchor="middle">' + opts.fmt(t) + "</text>"; });
    if (opts.zero !== undefined) inner += '<line x1="' + x(opts.zero) + '" x2="' + x(opts.zero) + '" y1="' + T + '" y2="' + (H - B) + '" stroke="var(--ink)" stroke-width="1.2"/>';
    if (opts.reference !== undefined && !isNaN(opts.reference)) inner += '<line x1="' + x(opts.reference) + '" x2="' + x(opts.reference) + '" y1="' + T + '" y2="' + (H - B) + '" stroke="var(--ink)" stroke-dasharray="5 4"/>';
    rows.forEach(function (row, i) {
      var y = T + i * rowH + rowH / 2;
      inner += '<text x="' + (L - 10) + '" y="' + (y + 4) + '" class="lab" text-anchor="end">' + esc(row.label) + "</text>";
      row.series.forEach(function (s, k) {
        var dy = row.series.length > 1 ? (k === 0 ? -7 : 7) : 0;
        if (s.est === null || isNaN(s.est)) return;
        if (s.lo !== null && !isNaN(s.lo)) inner += '<line x1="' + x(s.lo) + '" x2="' + x(s.hi) + '" y1="' + (y + dy) + '" y2="' + (y + dy) + '" stroke="' + s.color + '" stroke-width="2.4"/>';
        var fill = s.hollow ? "var(--panel)" : s.color;
        inner += s.shape === "square" ?
          '<rect x="' + (x(s.est) - 5) + '" y="' + (y + dy - 5) + '" width="10" height="10" fill="' + fill + '" stroke="' + s.color + '" stroke-width="2"><title>' + esc(s.tip) + "</title></rect>" :
          '<circle cx="' + x(s.est) + '" cy="' + (y + dy) + '" r="5.5" fill="' + fill + '" stroke="' + s.color + '" stroke-width="2"><title>' + esc(s.tip) + "</title></circle>";
      });
      inner += '<text x="' + (W - R + 16) + '" y="' + (y + 4) + '" class="axis">' + esc(row.note || "") + "</text>";
    });
    return svg(W, H, opts.label, inner);
  }

  function visibleGroups() {
    var est = byGroup(D.undiagnosis);
    return GROUPS.filter(function (g) { return !state.hidden[g] && !(state.hideSmall && est[g].small_n_warning); });
  }
  function groupChecks() {
    return '<div class="controls" role="group" aria-label="Groups shown">' + GROUPS.map(function (g) {
      return '<label class="check"><input type="checkbox" data-group="' + esc(g) + '"' + (state.hidden[g] ? "" : " checked") + "> " + esc(g) + "</label>"; }).join("") +
      '<label class="check"><input type="checkbox" id="hide-small"' + (state.hideSmall ? " checked" : "") + "> Hide small samples</label></div>";
  }

  /* ---------- pages ---------- */
  function pageOverview() {
    var est = byGroup(D.undiagnosis), std = byGroup(D.age_standardized), con = byGroup(D.contrasts);
    var all = est[ALL], c = con[D.meta.comparison_group];
    var groups = visibleGroups();
    var rows = groups.map(function (g) {
      var e = est[g], s = std[g], useStd = state.standardized;
      var lo = useStd ? s.ci_low : (state.interval === "logit" ? e.ci_low_logit : e.ci_low_wald);
      var hi = useStd ? s.ci_high : (state.interval === "logit" ? e.ci_high_logit : e.ci_high_wald);
      var value = useStd ? s.age_standardized_estimate : e.estimate;
      return { label: g, note: "n = " + e.respondents + ", effective n = " + Math.round(e.effective_n_kish) + (e.small_n_warning ? "  small sample" : ""),
        series: [{ est: value * 100, lo: lo * 100, hi: hi * 100, color: "var(--c1)", hollow: e.small_n_warning, tip: g + ": " + pct(value) + " (" + pct(lo) + " to " + pct(hi) + ")" }] };
    });
    var html = '<div class="box note"><strong>Denominator.</strong> People whose HbA1c is 6.5% or higher. "Never told" means they answered no to being told by a doctor that they have diabetes. Estimates are survey-weighted and describe the US population; respondent counts are sample sizes only.</div>' +
      '<div class="cards">' +
      card("Never told (all groups)", pct(all.estimate), "95% CI " + pct(all.ci_low_logit) + " to " + pct(all.ci_high_logit)) +
      card("HbA1c-positive respondents", num(all.respondents), mil(all.weighted_denominator) + " people once weighted; effective n " + Math.round(all.effective_n_kish)) +
      card("Gap, Black vs White", pp(c.difference), "95% CI " + pp(c.ci_low) + " to " + pp(c.ci_high) + ", " + pval(c.p_value) + ". Confirmatory, pre-specified") + "</div>" +
      groupChecks() +
      '<div class="controls"><label>Interval<select id="interval"><option value="logit"' + (state.interval === "logit" ? " selected" : "") + '>Logit (survey default)</option><option value="wald"' + (state.interval === "wald" ? " selected" : "") + ">Wald</option></select></label>" +
      '<label class="check"><input type="checkbox" id="std"' + (state.standardized ? " checked" : "") + "> Age-standardized to the HbA1c-positive age mix</label></div>" +
      '<div class="panel wide"><h2>Share never told they have diabetes, by group</h2>' +
      (rows.length ? dotChart(rows, { min: 0, max: 70, ticks: [0, 10, 20, 30, 40, 50, 60, 70], fmt: function (t) { return t + "%"; }, reference: all.estimate * 100, label: "Undiagnosed share by group with 95% intervals" }) : '<p class="note">No groups selected.</p>') +
      '<p class="note">Dashed line is the all-groups estimate. Hollow markers have fewer than ' + D.meta.min_positives + " respondents or an effective sample under " + D.meta.min_effective_n + ".</p></div>" +
      '<div class="panel wide"><h2>Estimates and denominators</h2>' + table(["Group", "Respondents", "Weighted denominator", "Effective n", "Never told", "95% CI (logit)", "Age-standardized"],
        groups.concat([ALL]).map(function (g) {
          var e = est[g]; return [esc(g) + (e.small_n_warning ? flag("small sample") : ""), num(e.respondents), mil(e.weighted_denominator), Math.round(e.effective_n_kish), pct(e.estimate), pct(e.ci_low_logit) + " to " + pct(e.ci_high_logit), pct(std[g].age_standardized_estimate)]; }), [1, 2, 3, 4, 5, 6]) + "</div>" +
      '<div class="panel wide"><h2>Each group against ' + esc(D.meta.reference_group) + '</h2><p class="note">Only the Black vs White comparison was pre-specified. The others are exploratory and shown with Holm-adjusted p-values.</p>' +
      table(["Group", "Difference", "95% CI", "Ratio", "p", "Holm p", "Analysis"], D.contrasts.map(function (r) {
        return [esc(r.group), pp(r.difference), pp(r.ci_low) + " to " + pp(r.ci_high), r.ratio.toFixed(2), pval(r.p_value), pval(r.p_value_holm), esc(r.analysis_type)]; }), [1, 2, 3, 4, 5]) + "</div>" +
      '<div class="panel wide"><h2>Robustness to cohort definition</h2>' + table(["Analysis", "Cohort", "HbA1c positive", "Black", "White", "Difference (95% CI)", "Ratio", "p"], D.robustness.map(function (r) {
        return [esc(r.analysis), num(r.cohort_respondents), num(r.hba1c_positive), pct(r.comparison_estimate), pct(r.reference_estimate), pp(r.difference) + " (" + pp(r.ci_low) + " to " + pp(r.ci_high) + ")", r.ratio.toFixed(2), pval(r.p_value)]; }), [1, 2, 3, 4, 5, 6]) + "</div>";
    return html;
  }

  function modelSelect() {
    return '<label>Model<select id="model">' + Object.keys(MODEL_NAMES).map(function (m) { return '<option value="' + m + '"' + (state.model === m ? " selected" : "") + ">" + esc(MODEL_NAMES[m]) + "</option>"; }).join("") + "</select></label>";
  }
  function pageModels() {
    var metric = state.metric, sub = D.subgroup_metrics.filter(function (r) { return r.model === state.model; });
    function get(label, g) { return sub.filter(function (r) { return r.label === label && r.group === g; })[0]; }
    var groups = visibleGroups().concat([ALL]);
    var rows = groups.map(function (g) {
      var a = get("diagnosed", g), b = get("hba1c_pos", g);
      return { label: g, note: a.positives + " positives" + (a.small_n_warning ? "  small sample" : ""), series: [
        { est: a[metric] * 100, lo: a[metric + "_ci_low"] * 100, hi: a[metric + "_ci_high"] * 100, color: "var(--c1)", hollow: a.small_n_warning, tip: g + " diagnosed label: " + pct(a[metric]) },
        { est: b[metric] * 100, lo: b[metric + "_ci_low"] * 100, hi: b[metric + "_ci_high"] * 100, color: "var(--c2)", shape: "square", hollow: b.small_n_warning, tip: g + " HbA1c label: " + pct(b[metric]) }] };
    });
    var cost = D.specificity_cost.filter(function (r) { return r.model === state.model; });
    var costRows = groups.map(function (g) { var r = cost.filter(function (x) { return x.group === g; })[0];
      return { label: g, note: "", series: [{ est: r.cost * 100, lo: r.ci_low * 100, hi: r.ci_high * 100, color: "var(--c1)", tip: g + ": " + pp(r.cost) }] }; });
    var auc = D.auc_difference.filter(function (r) { return r.model === state.model; })[0];
    var thr = D.thresholds.filter(function (r) { return r.model === state.model; });
    var metricNames = { sensitivity: "Sensitivity", specificity: "Specificity", ppv: "Positive predictive value", npv: "Negative predictive value" };
    var raceNote = state.model.indexOf("race") >= 0 ? '<div class="box warn">Race is a model input here. This is a sensitivity analysis: using race as a predictor while auditing performance by race needs explicit justification.</div>' : "";
    return '<div class="box warn"><strong>Not a clinical tool.</strong> These models use a few coarse inputs to compare two training labels. They are not risk models and are not ready for clinical use.</div>' + raceNote +
      '<div class="controls">' + modelSelect() + '<label>Metric<select id="metric">' + Object.keys(metricNames).map(function (m) { return '<option value="' + m + '"' + (metric === m ? " selected" : "") + ">" + metricNames[m] + "</option>"; }).join("") + "</select></label></div>" + groupChecks() +
      '<div class="panel wide"><h2>' + metricNames[metric] + " against the HbA1c criterion</h2>" + dotChart(rows, { min: 0, max: 100, ticks: [0, 20, 40, 60, 80, 100], fmt: function (t) { return t + "%"; }, rowH: 52, label: metricNames[metric] + " by group for both training labels" }) +
      '<div class="legend"><span><i style="background:var(--c1)"></i>Trained on diagnosed label</span><span><i style="background:var(--c2);border-radius:2px"></i>Trained on HbA1c label</span></div>' +
      '<p class="note">95% percentile intervals from the Rao-Wu PSU bootstrap on out-of-fold predictions. Hollow markers are small samples.</p></div>' +
      '<div class="panel wide"><h2>Specificity cost, percentage points</h2>' + dotChart(costRows, { min: -15, max: 15, ticks: [-15, -10, -5, 0, 5, 10, 15], fmt: function (t) { return t; }, zero: 0, rightPad: 40, rowH: 40, label: "Specificity cost by group" }) +
      '<p class="note">Cost = specificity of the diagnosed-label model minus the HbA1c-label model. Positive means more false positives when training on the HbA1c label.</p></div>' +
      '<div class="panel wide"><h2>Discrimination and thresholds</h2>' + table(["Quantity", "Value"], [
        ["AUC, diagnosed label", auc.auc_diagnosed_label.toFixed(3)], ["AUC, HbA1c label", auc.auc_hba1c_label.toFixed(3)],
        ["Difference (95% CI)", (auc.difference >= 0 ? "+" : "") + auc.difference.toFixed(3) + " (" + auc.ci_low.toFixed(3) + " to " + auc.ci_high.toFixed(3) + ")"],
        ["Paired bootstrap", pval(auc.p_value_bootstrap)]].concat(thr.map(function (t) { return ["Mean nested threshold, " + (t.label === "diagnosed" ? "diagnosed label" : "HbA1c label"), t.mean.toFixed(3) + " (sd " + t.sd.toFixed(3) + ")"]; })), [1]) +
      '<p class="note">AUC is against the HbA1c criterion for both models. Thresholds are chosen inside each training fold, never on the test fold.</p></div>' +
      '<div class="panel wide"><h2>Group detail</h2>' + table(["Group", "Label", "Positives (effective n)", "Sensitivity", "Specificity", "PPV", "NPV"], groups.reduce(function (acc, g) {
        ["diagnosed", "hba1c_pos"].forEach(function (l) { var r = get(l, g);
          acc.push([esc(g) + (r.small_n_warning ? flag("small sample") : ""), l === "diagnosed" ? "Diagnosed" : "HbA1c", r.positives + " (" + Math.round(r.effective_n_positives) + ")", pct(r.sensitivity) + " (" + pct(r.sensitivity_ci_low, 0) + " to " + pct(r.sensitivity_ci_high, 0) + ")", pct(r.specificity) + " (" + pct(r.specificity_ci_low, 0) + " to " + pct(r.specificity_ci_high, 0) + ")", pct(r.ppv), pct(r.npv)]); });
        return acc; }, []), [2, 3, 4, 5, 6]) + "</div>";
  }

  function pageMethods() {
    var att = D.attrition, max = att[0].n;
    var bars = att.map(function (r) { return '<tr><td>' + r.step + '. ' + esc(r.description) + '</td><td class="num">' + num(r.n) + '</td><td class="num">' + (r.removed ? "-" + num(r.removed) : "") + '</td><td style="width:32%"><div style="background:var(--c1);height:10px;border-radius:5px;width:' + (r.n / max * 100).toFixed(1) + '%" role="img" aria-label="' + num(r.n) + ' remaining"></div></td></tr>'; }).join("");
    var miss = D.missingness.filter(function (r) { return r.variable === state.missingVar; });
    var passed = D.quality.filter(function (r) { return r.passed; }).length;
    var x = D.crosscheck;
    return '<div class="panel wide"><h2>Cohort flow</h2><div class="table-wrap"><table><thead><tr><th scope="col">Step</th><th class="num" scope="col">Remaining</th><th class="num" scope="col">Removed</th><th scope="col"></th></tr></thead><tbody>' + bars + "</tbody></table></div></div>" +
      '<div class="panel"><h2>Survey design</h2><ul class="tight"><li>Weight: <code>WTMEC2YR</code>, the exam weight, because every analysis variable comes from the examined sample. The fasting subsample weight is not needed and fasting glucose is not used.</li>' +
      "<li>Strata <code>SDMVSTRA</code> and PSUs <code>SDMVPSU</code> define the variance. Subgroups are subpopulations of the full design, not separate surveys.</li>" +
      "<li>Degrees of freedom are PSUs minus strata with positive weight in the subgroup. Logit intervals use a t quantile on those degrees of freedom.</li>" +
      "<li>Model intervals use a Rao-Wu rescaled bootstrap: one PSU drawn per two-PSU stratum.</li></ul></div>" +
      '<div class="panel"><h2>Data quality</h2><p class="' + (passed === D.quality.length ? "ok" : "bad") + '">' + passed + " of " + D.quality.length + " SQL checks passed</p>" +
      table(["Check", "Result"], D.quality.map(function (r) { return [esc(r.check_name), (r.passed ? "pass: " : "FAIL: ") + esc(r.detail)]; })) + "</div>" +
      '<div class="controls"><label>Variable<select id="missing">' + ["bmi", "family_history", "insured", "routine_care"].map(function (v) { return '<option value="' + v + '"' + (state.missingVar === v ? " selected" : "") + ">" + v + "</option>"; }).join("") + "</select></label></div>" +
      '<div class="panel wide"><h2>Missing values by group, ' + esc(state.missingVar) + "</h2>" + table(["Group", "Respondents", "Missing", "Share missing"], miss.map(function (r) { return [esc(r.group), num(r.respondents), num(r.missing), pct(r.missing_share)]; }), [1, 2, 3]) +
      '<p class="note">Family history is only asked of adults 20 and older, so it is blank for adolescents by design. Models handle it with imputation and a missing indicator.</p></div>' +
      '<div class="panel"><h2>R cross-check</h2>' + (x.length ? '<p class="ok">' + x.filter(function (r) { return r.status === "pass"; }).length + " of " + x.length + " Python estimates match R survey within " + x[0].tolerance + "</p>" : "<p>Not run.</p>") + "</div>" +
      '<div class="panel"><h2>Limits</h2><ul class="tight"><li>Descriptive: the gap could reflect access, screening frequency, clinician behavior or measurement. This data cannot separate them.</li><li>HbA1c can read high in some people with sickle cell trait; no such variable is available.</li><li>Small groups have wide intervals and are flagged, not hidden.</li><li>Subgroup comparisons other than Black vs White are exploratory.</li></ul></div>';
  }

  function render() {
    document.getElementById("view").innerHTML = { overview: pageOverview, models: pageModels, methods: pageMethods }[state.tab]();
    document.querySelectorAll("[data-tab]").forEach(function (t) { var on = t.getAttribute("data-tab") === state.tab; t.setAttribute("aria-selected", on ? "true" : "false"); t.tabIndex = on ? 0 : -1; });
    document.getElementById("status").textContent = D.meta.sample;
  }
  function set(p) { Object.keys(p).forEach(function (k) { state[k] = p[k]; }); var a = document.activeElement && document.activeElement.id; render(); if (a) { var el = document.getElementById(a); if (el) el.focus(); } }
  document.addEventListener("change", function (ev) {
    var t = ev.target;
    if (t.id === "model") set({ model: t.value }); else if (t.id === "metric") set({ metric: t.value });
    else if (t.id === "interval") set({ interval: t.value }); else if (t.id === "std") set({ standardized: t.checked });
    else if (t.id === "hide-small") set({ hideSmall: t.checked }); else if (t.id === "missing") set({ missingVar: t.value });
    else if (t.hasAttribute("data-group")) { var h = Object.assign({}, state.hidden); h[t.getAttribute("data-group")] = !t.checked; set({ hidden: h }); }
  });
  document.addEventListener("click", function (ev) { var t = ev.target.closest("[data-tab]"); if (t) set({ tab: t.getAttribute("data-tab") }); });
  document.addEventListener("keydown", function (ev) {
    if (ev.target.hasAttribute && ev.target.hasAttribute("data-tab") && (ev.key === "ArrowRight" || ev.key === "ArrowLeft")) {
      var i = TABS.findIndex(function (x) { return x[0] === state.tab; }), n = (i + (ev.key === "ArrowRight" ? 1 : TABS.length - 1)) % TABS.length;
      set({ tab: TABS[n][0] }); document.getElementById("tab-" + TABS[n][0]).focus();
    }
  });
  document.getElementById("tabs").innerHTML = TABS.map(function (t) { return '<button type="button" role="tab" id="tab-' + t[0] + '" data-tab="' + t[0] + '" aria-selected="false">' + t[1] + "</button>"; }).join("");
  var hash = (location.hash || "").replace("#", ""); if (TABS.some(function (t) { return t[0] === hash; })) state.tab = hash;
  window.__state = state; window.__set = set;
  render();
})();
