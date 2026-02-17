#!/usr/bin/env node
// Earnings Monitor
// Polls Finnhub earnings calendar, alerts via OpenClaw when results come in.
// Usage: node monitor.js [--date YYYY-MM-DD] [--interval 90] [--duration 180]

const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

// --- Config ---
const ENV_PATH = path.join(__dirname, '..', '.env');
const STATE_PATH = path.join(__dirname, 'state.json');

function loadEnv() {
  if (!fs.existsSync(ENV_PATH)) return;
  for (const line of fs.readFileSync(ENV_PATH, 'utf8').split('\n')) {
    const m = line.match(/^([^#=]+)=(.*)$/);
    if (m) process.env[m[1].trim()] = m[2].trim();
  }
}
loadEnv();

const FINNHUB_KEY = process.env.FINNHUB_API_KEY;
if (!FINNHUB_KEY) { console.error('Missing FINNHUB_API_KEY'); process.exit(1); }

// --- Args ---
const args = process.argv.slice(2);
function arg(name, def) {
  const i = args.indexOf(`--${name}`);
  return i >= 0 && args[i + 1] ? args[i + 1] : def;
}

const today = new Date().toISOString().slice(0, 10);
const targetDate = arg('date', today);
const intervalSec = parseInt(arg('interval', '90'));
const durationMin = parseInt(arg('duration', '180'));
const endTime = Date.now() + durationMin * 60 * 1000;

console.log(`Earnings monitor started: date=${targetDate} interval=${intervalSec}s duration=${durationMin}m`);

// --- State ---
function loadState() {
  try { return JSON.parse(fs.readFileSync(STATE_PATH, 'utf8')); }
  catch { return { reported: {} }; }
}
function saveState(state) {
  fs.writeFileSync(STATE_PATH, JSON.stringify(state, null, 2));
}

// --- Finnhub ---
async function fetchEarnings(date) {
  const url = `https://finnhub.io/api/v1/calendar/earnings?from=${date}&to=${date}&token=${FINNHUB_KEY}`;
  const resp = await fetch(url);
  if (!resp.ok) throw new Error(`Finnhub ${resp.status}`);
  const data = await resp.json();
  return data.earningsCalendar || [];
}

// --- Alert ---
function sendAlert(message) {
  console.log(`ALERT: ${message}`);
  try {
    execSync(`openclaw message send --channel telegram --target "1007445801" --message "${message.replace(/"/g, '\\"')}"`, {
      timeout: 15000,
      stdio: 'pipe'
    });
  } catch (e) {
    // Fallback: write to a file for the agent to pick up
    console.error('Direct send failed, writing to alerts file');
    const alertsPath = path.join(__dirname, 'pending-alerts.txt');
    fs.appendFileSync(alertsPath, `${new Date().toISOString()} | ${message}\n`);
  }
}

// --- Main loop ---
async function poll() {
  const state = loadState();
  let earnings;
  
  try {
    earnings = await fetchEarnings(targetDate);
  } catch (e) {
    console.error(`Fetch error: ${e.message}`);
    return;
  }

  let newResults = 0;
  for (const e of earnings) {
    if (e.epsActual === null || e.epsActual === undefined) continue;
    
    const key = `${e.symbol}_${targetDate}`;
    if (state.reported[key]) continue;

    // New result!
    const est = e.epsEstimate;
    const actual = e.epsActual;
    const beat = est != null ? actual > est : null;
    const diff = est != null ? (actual - est).toFixed(4) : null;
    const pct = est != null && est !== 0 ? ((actual - est) / Math.abs(est) * 100).toFixed(1) : null;

    let emoji = '📊';
    let verdict = '';
    if (beat === true) { emoji = '🟢'; verdict = `BEAT by $${diff} (${pct}%)`; }
    else if (beat === false && actual < est) { emoji = '🔴'; verdict = `MISSED by $${Math.abs(diff)} (${pct}%)`; }
    else if (beat === false) { emoji = '🟡'; verdict = 'MET estimates'; }
    else { verdict = 'No estimate available'; }

    const revActual = e.revenueActual ? `$${(e.revenueActual / 1e9).toFixed(2)}B` : 'N/A';
    const revEst = e.revenueEstimate ? `$${(e.revenueEstimate / 1e9).toFixed(2)}B` : 'N/A';

    const msg = `${emoji} ${e.symbol} Earnings\nEPS: $${actual} vs $${est || 'N/A'} est → ${verdict}\nRevenue: ${revActual} vs ${revEst} est`;
    
    sendAlert(msg);
    state.reported[key] = { actual, estimate: est, time: new Date().toISOString() };
    newResults++;
  }

  if (newResults > 0) saveState(state);
  
  const pending = earnings.filter(e => e.epsActual === null || e.epsActual === undefined).length;
  const done = earnings.filter(e => e.epsActual !== null && e.epsActual !== undefined).length;
  console.log(`${new Date().toISOString()} | ${done} reported, ${pending} pending, ${newResults} new alerts`);
}

async function run() {
  // Initial state
  const state = loadState();
  if (!state.reported) state.reported = {};
  saveState(state);

  while (Date.now() < endTime) {
    await poll();
    await new Promise(r => setTimeout(r, intervalSec * 1000));
  }
  console.log('Monitor duration ended. Exiting.');
}

run().catch(e => { console.error(e); process.exit(1); });
