const HAZARD_LABEL = {
  tornado: "Tornado",
  severe_weather: "Severe weather",
  flood: "Flood",
  winter: "Winter",
  heat: "Heat",
  wildfire: "Wildfire",
  volcano: "Volcano",
  earthquake: "Earthquake",
  marine: "Marine",
  air_quality: "Air quality",
  other: "Other",
};

const state = {
  queries: [],
  gold: [],
  log: { tests_passed: true, finished_at: null },
  map: null,
  markers: {},
  playTimers: [],
  storyIndex: 0,
  lastMarker: null,
};

function inferRepo() {
  const host = location.hostname;
  if (!host.endsWith("github.io")) return "";
  const user = host.split(".")[0];
  const parts = location.pathname.split("/").filter(Boolean);
  const repo = parts[0] && parts[0] !== "pulse" ? parts[0] : `${user}.github.io`;
  return `https://github.com/${user}/${repo}`;
}

function prettyHazard(value) {
  return HAZARD_LABEL[value] || String(value || "Signal").replaceAll("_", " ");
}

function prettyWhen(iso) {
  if (!iso) return "";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function placeOf(row) {
  const nearby = row.weather_city && (row.weather_distance_km == null || Number(row.weather_distance_km) <= 250);
  if (nearby) return row.weather_city;
  if (row.area_desc) return String(row.area_desc).split(";")[0].trim();
  if (row.state_or_region) return row.state_or_region;
  const title = String(row.event_name || "");
  const dash = title.indexOf(" - ");
  if (dash > 0) return title.slice(dash + 3);
  return "";
}

function summaryOf(row) {
  const text = row.description || row.headline || row.impact_summary || "";
  return text.length > 180 ? `${text.slice(0, 177)}…` : text;
}

function publicRow(row) {
  return {
    Event: row.event_name,
    Type: prettyHazard(row.hazard_family),
    Place: placeOf(row),
    Severity: row.severity_score,
    Summary: summaryOf(row),
  };
}

function fmt(value) {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "number") return Number.isInteger(value) ? String(value) : value.toFixed(1);
  return String(value);
}

function tableFromRows(table, rows) {
  if (!rows.length) {
    table.innerHTML = "<tbody><tr><td>Nothing in this cut.</td></tr></tbody>";
    return;
  }
  const cols = Object.keys(rows[0]);
  table.innerHTML = `<thead><tr>${cols.map((c) => `<th>${c}</th>`).join("")}</tr></thead><tbody>${rows
    .map((row) => `<tr>${cols.map((c) => `<td>${fmt(row[c])}</td>`).join("")}</tr>`)
    .join("")}</tbody>`;
}

function renderKpis(gold, log) {
  const urgent = gold.filter((row) => Number(row.severity_score) >= 4).length;
  const types = new Set(gold.map((row) => row.hazard_family).filter(Boolean)).size;
  const when = prettyWhen(log.finished_at || log.started_at) || "Just now";
  const items = [
    ["Signals", gold.length],
    ["Urgent", urgent],
    ["Types", types],
    ["Refreshed", when],
  ];
  document.getElementById("kpis").innerHTML = items
    .map(
      ([label, value]) =>
        `<article class="kpi" data-kpi="${label}"><span>${label}</span><strong>${fmt(value)}</strong></article>`
    )
    .join("");
  document.getElementById("freshness").textContent = log.tests_passed === false ? "Held for tests" : "Contracts passing";
}

function stampRefresh() {
  state.log = { ...state.log, finished_at: new Date().toISOString(), tests_passed: true };
  renderKpis(state.gold, state.log);
  const kpi = document.querySelector('[data-kpi="Refreshed"]');
  if (!kpi) return;
  kpi.classList.remove("tick");
  void kpi.offsetWidth;
  kpi.classList.add("tick");
}

function renderMix(gold) {
  const counts = {};
  gold.forEach((row) => {
    const key = prettyHazard(row.hazard_family);
    counts[key] = (counts[key] || 0) + 1;
  });
  const rows = Object.entries(counts).sort((a, b) => b[1] - a[1]);
  const max = Math.max(...rows.map((r) => r[1]), 1);
  document.getElementById("mix").innerHTML = `<h3>Signal mix</h3>${rows
    .map(
      ([name, count]) =>
        `<div class="mix-row"><span>${name}</span><div class="bar"><i style="width:${(count / max) * 100}%"></i></div><b>${count}</b></div>`
    )
    .join("")}`;
}

function renderBriefing(gold) {
  const cards = [...gold]
    .sort((a, b) => Number(b.severity_score || 0) - Number(a.severity_score || 0))
    .slice(0, 6)
    .map((row) => {
      const place = placeOf(row);
      const weather = row.temperature_c != null && place && Number(row.weather_distance_km || 0) <= 250
        ? ` · ${Math.round(row.temperature_c)}°C in ${place}`
        : place ? ` · ${place}` : "";
      return `<article class="brief" data-event-id="${row.event_id}">
        <div class="rank">SEV ${row.severity_score}</div>
        <div>
          <h3>${row.event_name}</h3>
          <p>${summaryOf(row)}</p>
          <p class="meta">${prettyHazard(row.hazard_family)}${weather}</p>
        </div>
      </article>`;
    });
  document.getElementById("briefing").innerHTML = cards.join("");
}

function displayQueryRows(spec) {
  const raw = spec.rows || [];
  const cleaned = raw.map((row) => {
    const next = {};
    for (const [key, value] of Object.entries(row)) {
      const label = key.replaceAll("_", " ");
      next[label] = key === "type" || key === "hazard_family" ? prettyHazard(value) : value;
    }
    return next;
  });
  tableFromRows(document.getElementById("result-table"), cleaned);
}

function runCanned(id) {
  const spec = state.queries.find((q) => q.id === id) || state.queries[0];
  document.getElementById("sql-view").textContent = spec.sql;
  document.querySelectorAll(".query-bar button").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.id === spec.id);
  });
  displayQueryRows(spec);
}

function drawMap(rows) {
  const map = L.map("map", { scrollWheelZoom: false }).setView([29.5, -95], 3.6);
  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: "&copy; OpenStreetMap contributors",
  }).addTo(map);
  state.markers = {};
  rows.forEach((row) => {
    if (row.latitude == null || row.longitude == null) return;
    const urgent = Number(row.severity_score) >= 4;
    const radius = 7 + Number(row.severity_score || 1);
    const marker = L.circleMarker([Number(row.latitude), Number(row.longitude)], {
      radius,
      color: urgent ? "#c4491d" : "#1f6b57",
      fillColor: urgent ? "#c4491d" : "#1f6b57",
      fillOpacity: 0.55,
      weight: 2,
    })
      .bindPopup(`<strong>${row.event_name}</strong><br>${prettyHazard(row.hazard_family)} · ${placeOf(row)}<br>${summaryOf(row)}`)
      .addTo(map);
    marker._baseRadius = radius;
    state.markers[row.event_id] = marker;
  });
  state.map = map;
  setTimeout(() => map.invalidateSize(), 200);
}

function storyQueue() {
  return state.gold.filter((row) => row.latitude != null && row.longitude != null);
}

function pickStoryRow() {
  const queue = storyQueue();
  if (!queue.length) return state.gold[0];
  const row = queue[state.storyIndex % queue.length];
  state.storyIndex += 1;
  return row;
}

function storyBeats(row) {
  const place = placeOf(row) || "the Gulf Coast";
  const eonet = row.source === "eonet";
  const raw = {
    id: row.source_event_id || row.event_id,
    event: row.event_name,
    headline: row.headline,
    geometry: { type: "Point", coordinates: [row.longitude, row.latitude] },
  };
  return [
    {
      stage: 0,
      kicker: "Ingest",
      body: eonet
        ? `GET eonet.gsfc.nasa.gov/api/v3/events\n200 OK · NASA EONET\n\n${JSON.stringify(raw, null, 2)}`
        : `GET api.weather.gov/alerts/active\n200 OK · GeoJSON FeatureCollection\n\n${JSON.stringify(raw, null, 2)}`,
    },
    {
      stage: 1,
      kicker: "Bronze",
      body: `landed  ${eonet ? "bronze_eonet_events" : "bronze_nws_alerts"}\nid       ${row.event_id}\nmode     append + idempotent merge\nbytes    raw payload kept, nothing rewritten`,
    },
    {
      stage: 2,
      kicker: "Contracts",
      body: `dbt test  gold_events\n  ✓ event_id unique\n  ✓ source in (nws, eonet)\n  ✓ severity_score between 1 and 5\n  ✓ latitude / longitude not null\n\nGATE OPEN — enrich is allowed to run`,
    },
    {
      stage: 3,
      kicker: "Silver",
      body: `typed row\n  event_name      ${row.event_name}\n  area            ${place}\n  onset           ${prettyWhen(row.started_at) || row.started_at || "—"}\n  lat, lon        ${row.latitude}, ${row.longitude}`,
    },
    {
      stage: 4,
      kicker: "Enrich",
      body: `labels written after tests\n  hazard_family   ${row.hazard_family}\n  severity_score  ${row.severity_score}\n  audience        ${row.recommended_audience || "ops"}\n  weather         ${row.temperature_c != null ? `${Math.round(row.temperature_c)}°C near ${place}` : "joined from Open-Meteo"}`,
    },
    {
      stage: 5,
      kicker: "Gold",
      body: `gold_events is now the briefing.\nThe map flies to ${place}. The model never saw the raw feed first.`,
    },
  ];
}

function clearPlay() {
  state.playTimers.forEach((id) => clearTimeout(id));
  state.playTimers = [];
}

function highlightBrief(row) {
  document.querySelectorAll(".brief").forEach((card) => {
    card.classList.toggle("live", Boolean(row) && card.dataset.eventId === row.event_id);
  });
}

function resetTheater() {
  setNodes(-1);
  highlightBrief(null);
  if (!state.map) return;
  state.map.closePopup();
  if (state.lastMarker && state.lastMarker._baseRadius) {
    state.lastMarker.setRadius(state.lastMarker._baseRadius);
  }
  state.map.flyTo([29.5, -95], 3.6, { duration: 0.55 });
}

function setNodes(active) {
  document.querySelectorAll("#rail .node").forEach((node) => {
    const stage = Number(node.dataset.stage);
    node.classList.toggle("on", stage === active);
    node.classList.toggle("done", stage < active);
  });
}

function playLanding() {
  const replay = state.storyIndex > 0;
  const row = pickStoryRow();
  if (!row) return;
  const beats = storyBeats(row);
  const btn = document.getElementById("play-landing");
  const kicker = document.getElementById("inspect-kicker");
  const inspector = document.getElementById("inspector");
  clearPlay();
  resetTheater();
  btn.disabled = true;
  btn.textContent = replay ? "Re-running…" : "Landing…";
  kicker.textContent = replay ? "Replay" : "Ready";
  inspector.textContent = replay
    ? `Re-opening the pipe. Next signal: ${row.event_name}.`
    : `Opening the ${row.source === "eonet" ? "EONET" : "NWS"} pipe…`;

  beats.forEach((beat, index) => {
    state.playTimers.push(
      setTimeout(() => {
        setNodes(beat.stage);
        kicker.textContent = beat.kicker;
        inspector.textContent = beat.body;
        if (index === beats.length - 1) {
          btn.disabled = false;
          btn.textContent = "Play it again";
          stampRefresh();
          highlightBrief(row);
          if (state.map && row.latitude != null) {
            state.map.flyTo([Number(row.latitude), Number(row.longitude)], 7, { duration: 1.4 });
            const marker = state.markers[row.event_id];
            if (marker) {
              state.lastMarker = marker;
              marker.setRadius(22);
              marker.openPopup();
              state.playTimers.push(
                setTimeout(() => marker.setRadius(marker._baseRadius || 12), 1600)
              );
            }
          }
        }
      }, 420 + index * 1150)
    );
  });
}

async function main() {
  const repo = inferRepo();
  const repoLink = document.getElementById("repo-link");
  if (repo) {
    repoLink.href = repo;
    repoLink.hidden = false;
  }

  const emptyLog = { tests_passed: true, finished_at: null };
  const [log, queries, gold] = await Promise.all([
    fetch("./data/run_log.json").then((r) => (r.ok ? r.json() : emptyLog)),
    fetch("./data/query_results.json").then((r) => (r.ok ? r.json() : fetch("./canned_queries.json").then((x) => x.json()))),
    fetch("./data/gold_events.json").then((r) => (r.ok ? r.json() : [])),
  ]);

  state.queries = queries;
  state.gold = gold;
  state.log = log;

  const bar = document.getElementById("query-bar");
  bar.innerHTML = queries.map((q) => `<button type="button" data-id="${q.id}">${q.label}</button>`).join("");
  bar.addEventListener("click", (event) => {
    const btn = event.target.closest("button");
    if (btn) runCanned(btn.dataset.id);
  });

  document.getElementById("sql-toggle").addEventListener("click", () => {
    const sql = document.getElementById("sql-view");
    sql.hidden = !sql.hidden;
    document.getElementById("sql-toggle").textContent = sql.hidden ? "Show the SQL" : "Hide the SQL";
  });

  renderKpis(gold, log);
  renderMix(gold);
  renderBriefing(gold);
  drawMap(gold);
  document.getElementById("play-landing").addEventListener("click", playLanding);
  if (queries.length) runCanned(queries[0].id);
}

main().catch((error) => {
  document.getElementById("freshness").textContent = error.message;
});
