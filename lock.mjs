#!/usr/bin/env node
/**
 * lock.mjs — wrap a built dashboard HTML file in a password screen.
 *
 * The whole page is encrypted with AES-256-GCM using a key derived from your
 * password (PBKDF2-SHA256). The output file contains ONLY ciphertext + a small
 * unlock screen; the real data is never present in plaintext, so the file is
 * safe to host on any static host (even a public one). Decryption happens in
 * the browser via WebCrypto when the correct password is entered.
 *
 * Usage:
 *   LOCK_PASSWORD='your-strong-password' node lock.mjs <input.html> <output.html>
 *
 * Example:
 *   LOCK_PASSWORD='...' node lock.mjs dashboard.html docs/leads.html
 */
import fs from "node:fs";

const [, , inPath, outPath] = process.argv;
const password = process.env.LOCK_PASSWORD;
if (!inPath || !outPath || !password) {
  console.error("usage: LOCK_PASSWORD='your-password' node lock.mjs <input.html> <output.html>");
  process.exit(1);
}
if (password.length < 8) {
  console.error("Refusing to lock with a password shorter than 8 characters. Use a strong passphrase.");
  process.exit(1);
}

const ITER = 250000;
const data = fs.readFileSync(inPath); // raw bytes (UTF-8 html)
const salt = crypto.getRandomValues(new Uint8Array(16));
const iv = crypto.getRandomValues(new Uint8Array(12));

const km = await crypto.subtle.importKey("raw", new TextEncoder().encode(password), "PBKDF2", false, ["deriveKey"]);
const key = await crypto.subtle.deriveKey(
  { name: "PBKDF2", salt, iterations: ITER, hash: "SHA-256" },
  km, { name: "AES-GCM", length: 256 }, false, ["encrypt"]
);
const ct = new Uint8Array(await crypto.subtle.encrypt({ name: "AES-GCM", iv }, key, data));

const b64 = (u8) => Buffer.from(u8).toString("base64");
const payload = { salt: b64(salt), iv: b64(iv), iter: ITER, ct: b64(ct) };

const shell = `<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Lead Finder — Locked</title>
<style>
  *{box-sizing:border-box} html,body{margin:0;height:100%}
  body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
       background:linear-gradient(135deg,#4f46e5,#7c3aed);display:grid;place-items:center;min-height:100vh;color:#0f172a}
  .card{background:#fff;border-radius:18px;box-shadow:0 24px 60px rgba(0,0,0,.28);padding:30px 28px;width:min(380px,92vw);text-align:center}
  .mark{width:52px;height:52px;border-radius:14px;margin:0 auto 14px;background:linear-gradient(135deg,#4f46e5,#7c3aed);
        display:grid;place-items:center;color:#fff}
  h1{margin:0 0 4px;font-size:19px;font-weight:800;letter-spacing:-.02em}
  p{margin:0 0 18px;color:#64748b;font-size:13px}
  input{width:100%;padding:12px 13px;border:1px solid #e6e9f2;border-radius:11px;font-size:15px;outline:none}
  input:focus{border-color:#4f46e5;box-shadow:0 0 0 4px rgba(79,70,229,.16)}
  button{width:100%;margin-top:12px;padding:12px;border:none;border-radius:11px;cursor:pointer;font-size:15px;font-weight:700;color:#fff;
         background:linear-gradient(135deg,#4f46e5,#7c3aed)}
  button:disabled{opacity:.6;cursor:default}
  .err{color:#dc2626;font-size:13px;margin-top:10px;min-height:18px}
</style></head>
<body>
  <form class="card" id="f" autocomplete="off">
    <div class="mark"><svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg></div>
    <h1>Lead Finder</h1>
    <p>Enter the password to view the dashboard.</p>
    <input id="pw" type="password" placeholder="Password" autofocus>
    <button id="go" type="submit">Unlock</button>
    <div class="err" id="err"></div>
  </form>
<script>
const PAYLOAD = ${JSON.stringify(payload)};
const b64d = s => Uint8Array.from(atob(s), c => c.charCodeAt(0));
async function decrypt(pw){
  const km = await crypto.subtle.importKey("raw", new TextEncoder().encode(pw), "PBKDF2", false, ["deriveKey"]);
  const key = await crypto.subtle.deriveKey(
    { name:"PBKDF2", salt:b64d(PAYLOAD.salt), iterations:PAYLOAD.iter, hash:"SHA-256" },
    km, { name:"AES-GCM", length:256 }, false, ["decrypt"]);
  const buf = await crypto.subtle.decrypt({ name:"AES-GCM", iv:b64d(PAYLOAD.iv) }, key, b64d(PAYLOAD.ct));
  return new TextDecoder().decode(buf);
}
async function unlock(pw){
  const html = await decrypt(pw);              // throws on wrong password (GCM auth fail)
  try{ sessionStorage.setItem("lf_pw", pw); }catch(e){}
  document.open(); document.write(html); document.close();
}
const $ = id => document.getElementById(id);
$("f").addEventListener("submit", async e => {
  e.preventDefault();
  $("go").disabled = true; $("err").textContent = "";
  try { await unlock($("pw").value); }
  catch(err){ $("err").textContent = "Wrong password. Try again."; $("go").disabled = false; $("pw").select(); }
});
// Auto-unlock within the same browser session (cleared when the tab closes).
(async () => { try { const p = sessionStorage.getItem("lf_pw"); if (p) await unlock(p); } catch(e){ try{sessionStorage.removeItem("lf_pw");}catch(_){} } })();
</script>
</body></html>
`;

fs.writeFileSync(outPath, shell);
const kb = (s) => (s / 1024).toFixed(0) + " KB";
console.log(`Locked ${inPath} (${kb(data.length)}) -> ${outPath} (${kb(Buffer.byteLength(shell))}), PBKDF2 ${ITER} iters, AES-256-GCM.`);
