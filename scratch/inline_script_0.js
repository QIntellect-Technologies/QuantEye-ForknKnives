
var API_BASE = window.location.origin + "/api";
let multiTickerInterval;
let _lastMultiTickerKey = null;

async function startAllStreams() {
    const grid = document.getElementById('multiCameraGrid');
    if (!grid) return;
    try {
        const resp = await fetch(`${API_BASE}/cameras?active_only=true`);
        const cameras = await resp.json();
        if (!cameras || cameras.length === 0) {
            grid.innerHTML = '<div style="grid-column: 1/-1; padding: 30px; text-align: center; color: var(--text-secondary);">No cameras configured yet. Add cameras in System Settings.</div>';
            return;
        }
        grid.innerHTML = cameras.map(c => `
          <div class="cctv-screen-wrapper" style="margin: 0; padding: 0;">
            <div class="cctv-badge" style="display:flex;">
              <span class="cctv-badge-dot"></span>${c.name} &bull; ${c.room_name}
            </div>
            <div class="cctv-viewport" style="background: #000; min-height: 240px;">
              <img id="multiStream_${c.camera_id}" src="/api/stream/${c.camera_id}?t=${new Date().getTime()}" style="width:100%; height:100%; object-fit:cover; display:block;" onerror="this.style.display='none'; document.getElementById('ph_${c.camera_id}').style.display='flex';" />
              <div id="ph_${c.camera_id}" style="display:none; align-items:center; justify-content:center; flex-direction:column; height:100%; color:var(--text-secondary);">
                <i class="fa-solid fa-video-slash" style="font-size:2em; margin-bottom:8px;"></i>
                <span style="font-size:0.8em;">Camera Offline</span>
              </div>
            </div>
          </div>
        `).join('');

        document.getElementById('multiStreamMessage').innerHTML = `<div class="success"><i class="fa-solid fa-check-circle"></i> Monitoring active on ${cameras.length} camera feed(s).</div>`;
        _lastMultiTickerKey = null;
        if (multiTickerInterval) clearInterval(multiTickerInterval);
        multiTickerInterval = setInterval(fetchMultiLiveDetections, 1500);
        fetchMultiLiveDetections();
    } catch(err) {
        document.getElementById('multiStreamMessage').innerHTML = `<div class="warning">Notice: ${err.message}</div>`;
    }
}

function stopAllStreams() {
    const grid = document.getElementById('multiCameraGrid');
    if (grid) {
      grid.querySelectorAll('img').forEach(img => { img.src = ""; img.style.display = 'none'; });
      grid.querySelectorAll('[id^="ph_"]').forEach(ph => ph.style.display = 'flex');
    }
    document.getElementById('multiStreamMessage').innerHTML = '';
    if (multiTickerInterval) { clearInterval(multiTickerInterval); multiTickerInterval = null; }
    _lastMultiTickerKey = null;
        document.getElementById("multiTickerList").innerHTML =
            '<p style="text-align:center;color:var(--text-secondary);margin-top:30px;font-size:0.85em;">Feed standby.</p>';
    }

async function fetchMultiLiveDetections() {
    try {
        const resp = await fetch(`${API_BASE}/live-detections`);
        const data = await resp.json();
        loadStats();
        const list = document.getElementById("multiTickerList");

        if (!data.detections || data.detections.length === 0) {
            if (_lastMultiTickerKey !== '') {
                _lastMultiTickerKey = '';
                list.innerHTML = '<p style="text-align:center;color:var(--text-secondary);margin-top:30px;font-size:0.85em;">Awaiting matches...</p>';
            }
            return;
        }

        // Build a cache-key from ids+timestamps — only re-render if something changed
        const key = data.detections.map(d => d.user_id + ':' + d.timestamp).join('|');
        if (key === _lastMultiTickerKey) return;
        _lastMultiTickerKey = key;

        list.innerHTML =
            `<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">` +
            data.detections.map((log) => {
                const isUnknown = log.name === "Unknown";
                const initials = log.name.split(" ").map(n => n[0] || "?").join("").toUpperCase().slice(0, 2);
                const pct = Math.round((log.confidence || 0) * 100);
                const time = log.timestamp ? formatMainTime(log.timestamp) : new Date().toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
                const userId = log.user_id;
                const dept = log.department || "";
                const sourceStr = log.source === "stream_nvr_office" ? "NVR" : log.source === "stream_dvr_office" ? "DVR" : "Webcam";
                const confColor = pct >= 80 ? "#16a34a" : pct >= 60 ? "#b45309" : "#dc2626";
                const accentColor = isUnknown ? "#94a3b8" : pct >= 80 ? "#3aafa9" : pct >= 60 ? "#f59e0b" : "#ef4444";
                const avatarBg = isUnknown ? "background:linear-gradient(135deg,#94a3b8,#64748b);" : "background:linear-gradient(135deg,#3aafa9,#1d8a84);";
                const photoHTML = userId
                    ? `<img src="/profile_photos/user_${userId}.jpg" style="width:100%;height:100%;object-fit:cover;border-radius:9px;" onerror="this.style.display='none';this.nextElementSibling.style.display='flex';" /><span style="display:none;width:100%;height:100%;align-items:center;justify-content:center;font-weight:800;color:#fff;">${initials}</span>`
                    : `<span style="font-weight:800;color:#fff;">${initials}</span>`;

                return `
                <div style="background:#fff;border:1px solid #e2e8f0;border-left:4px solid ${accentColor};border-radius:12px;overflow:hidden;">
                  <div style="padding:13px 14px;display:flex;flex-direction:column;gap:8px;">
                    <div style="display:flex;align-items:center;gap:10px;">
                      <div style="position:relative;flex-shrink:0;">
                        <div style="width:120px;height:120px;border-radius:10px;${avatarBg}display:flex;align-items:center;justify-content:center;overflow:hidden;border:2px solid #e2e8f0;">${photoHTML}</div>
                        <span style="position:absolute;bottom:-2px;right:-2px;width:12px;height:12px;border-radius:50%;border:2px solid #fff;background:${isUnknown ? "#94a3b8" : "#22c55e"};"></span>
                      </div>
                      <div style="flex:1;min-width:0;">
                        <div style="font-size:0.88em;font-weight:800;color:#0f172a;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${log.name}</div>
                        ${dept ? `<div style="font-size:0.69em;color:#3aafa9;font-weight:700;margin-top:2px;">${dept}</div>` : ""}
                        <div style="font-size:0.63em;color:#64748b;font-family:'JetBrains Mono',monospace;margin-top:2px;">${userId ? `EMP-${String(userId).padStart(3, "0")}` : "N/A"}</div>
                        <div style="font-size:0.61em;color:#94a3b8;margin-top:2px;display:flex;gap:8px;">
                          <span><i class="fa-solid fa-clock" style="color:#3aafa9;margin-right:2px;font-size:0.9em;"></i>${time}</span>
                          <span><i class="fa-solid fa-camera" style="color:#3aafa9;margin-right:2px;font-size:0.9em;"></i>${sourceStr}</span>
                        </div>
                      </div>
                    </div>
                    <div style="height:1px;background:#e2e8f0;"></div>
                    <div style="display:flex;align-items:center;justify-content:space-between;">
                      <div style="display:flex;align-items:center;gap:4px;font-size:0.63em;color:#64748b;">
                        <i class="fa-solid fa-clock" style="color:#3aafa9;"></i>${time}
                      </div>
                      <div style="display:inline-flex;align-items:center;gap:4px;font-size:0.62em;font-weight:800;padding:3px 9px;border-radius:6px;${isUnknown ? "background:#fef2f2;border:1px solid #fecaca;color:#dc2626;" : "background:#f0fdf4;border:1px solid #bbf7d0;color:#15803d;}"}">
                        <i class="fa-solid ${isUnknown ? "fa-circle-exclamation" : "fa-circle-check"}"></i>${isUnknown ? "Unknown" : "Marked"}
                      </div>
                    </div>
                  </div>
                </div>`;
            }).join("") +
            `</div>`;
    } catch (e) {
        console.error("Multi-ticker update error:", e);
    }
}
