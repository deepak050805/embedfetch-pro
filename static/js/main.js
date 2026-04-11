// MVP Logic tracking Single and Playlist Downloader with Quality extraction

document.addEventListener('DOMContentLoaded', async () => {
    // Check FFmpeg status on load
    try {
        const res = await fetch('/api/system_status');
        const data = await res.json();
        if (!data.ffmpeg_installed) {
            const warnBox = document.getElementById('ffmpegWarning');
            if (warnBox) warnBox.classList.remove('hidden');
        }
    } catch (e) {
        console.error('Could not check system status');
    }
});


// ================================
// Step 1: Analyze Video
// ================================
const analyzeForm = document.getElementById('singleAnalyzeForm');
if (analyzeForm) {
    analyzeForm.addEventListener('submit', async (e) => {
        e.preventDefault();

        const url = document.getElementById('videoUrl').value;
        const btnText = document.getElementById('analyzeBtnText');
        const spinner = document.getElementById('analyzeLoadingSpinner');
        const errText = document.getElementById('analyzeError');
        const qBlock = document.getElementById('qualitySelectorBlock');
        const formatsGrid = document.getElementById('formatsGrid');

        btnText.textContent = 'Analyzing...';
        spinner.classList.remove('hidden');
        errText.classList.add('hidden');
        qBlock.classList.add('hidden');

        try {
            const res = await fetch('/api/formats', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({url: url})
            });

            const data = await res.json();

            if (data.status === 'success') {
                const childrenArray = Array.from(formatsGrid.children);
                for (let i = 1; i < childrenArray.length; i++) {
                    formatsGrid.removeChild(childrenArray[i]);
                }

                if (data.formats && Array.isArray(data.formats)) {
                    data.formats.forEach(f => {
                        const lbl = document.createElement('label');
                        lbl.className = 'cursor-pointer';
                        lbl.innerHTML = `
                            <input type="radio" name="formatSelector" value="${f.format_id}" class="peer sr-only">
                            <div class="rounded-xl p-4 bg-dark-800 border border-white/10 peer-checked:border-pink-500 peer-checked:bg-pink-900/20 hover:border-white/30 transition-all text-left">
                                <div class="font-bold text-gray-200 text-lg mb-1">${f.resolution} <span class="text-sm font-normal text-gray-400">@ ${f.fps}fps</span></div>
                                <div class="text-xs text-gray-400">${f.ext.toUpperCase()} | Codec: ${f.vcodec}</div>
                                <div class="text-xs text-pink-400 mt-1">${f.filesize} • ${f.bitrate}</div>
                            </div>
                        `;
                        formatsGrid.appendChild(lbl);
                    });
                }

                qBlock.classList.remove('hidden');
            } else {
                throw new Error(data.message || 'Error extracting formats');
            }

        } catch (err) {
            errText.textContent = 'Playback error: ' + err.message;
            errText.classList.remove('hidden');
        } finally {
            btnText.textContent = 'Analyze Quality Formats';
            spinner.classList.add('hidden');
        }
    });
}


// ================================
// Step 2: FIXED DOWNLOAD (ONLY ERROR FIXED HERE)
// ================================
const singleForm = document.getElementById('singleDownloadForm');
if (singleForm) {
    singleForm.addEventListener('submit', async (e) => {
        e.preventDefault();

        const url = document.getElementById('videoUrl').value;
        const selectorVal = document.querySelector('input[name="formatSelector"]:checked');
        const formatId = selectorVal ? selectorVal.value : 'best';

        const btnText = document.getElementById('btnText');
        const spinner = document.getElementById('loadingSpinner');
        const progressContainer = document.getElementById('progressContainer');
        const dlStatus = document.getElementById('dlStatus');
        const dlStats = document.getElementById('dlStats');
        const bar = document.getElementById('dlProgressBar');

        btnText.textContent = 'Downloading...';
        spinner.classList.remove('hidden');
        progressContainer.classList.remove('hidden');
        dlStatus.classList.remove('text-red-400', 'text-green-400');
        dlStatus.classList.add('text-purple-400');
        dlStatus.textContent = 'Preparing download...';
        dlStats.textContent = 'Please wait while file is generated...';
        bar.style.width = '50%';

        try {
            const response = await fetch('/api/download/single', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    url: url,
                    format_id: formatId
                })
            });

            if (!response.ok) {
                const errData = await response.json().catch(() => null);
                throw new Error(errData && errData.detail ? errData.detail : "Download failed.");
            }

            const resultData = await response.json();
            
            // 🔥 ONLY CHANGE DONE HERE
            if (resultData.status === 'proxy' && resultData.proxy_url) {
            window.location.href = resultData.proxy_url;
            } else 
        {
            throw new Error("Download failed");
        }

            dlStatus.textContent = 'Downloading merged video...';
            dlStatus.classList.replace('text-purple-400', 'text-green-400');
            dlStats.textContent = 'Audio + Video merged using FFmpeg';
            bar.style.width = '100%';

        } catch (err) {
            dlStatus.textContent = 'Error: ' + err.message;
            dlStatus.classList.replace('text-purple-400', 'text-red-400');
            dlStats.textContent = '';
            bar.style.width = '0%';
            
            btnText.textContent = 'Start New Download';
            spinner.classList.add('hidden');
        }
    });
}


// ================================
// Playlist UI (unchanged)
// ================================
const playlistForm = document.getElementById('playlistForm');
if (playlistForm) {
    playlistForm.addEventListener('submit', async (e) => {
        e.preventDefault();

        const url = document.getElementById('playlistUrl').value;
        const btnText = document.getElementById('pBtnText');
        const spinner = document.getElementById('pLoadingSpinner');
        const progressContainer = document.getElementById('pProgressContainer');
        const dlStatus = document.getElementById('pStatus');
        const dlStats = document.getElementById('pStats');
        const bar = document.getElementById('pProgressBar');
        const listContainer = document.getElementById('playlistItems');
        const listUl = document.getElementById('videosList');

        btnText.textContent = 'Fetching Playlist...';
        spinner.classList.remove('hidden');
        listContainer.classList.add('hidden');

        try {
            const resExt = await fetch('/api/playlist/extract', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({url: url})
            });

            const dataExt = await resExt.json();

            if (dataExt.status === 'success') {
                listContainer.classList.remove('hidden');
                listUl.innerHTML = dataExt.videos.map(v =>
                    `<li class="bg-dark-900/80 p-3 rounded-lg flex justify-between border border-white/5">
                        <span class="truncate font-medium text-gray-200">${v.title}</span>
                    </li>`
                ).join('');

                progressContainer.classList.remove('hidden');
                dlStatus.textContent = 'Downloading all videos & Compressing...';
                dlStatus.classList.add('text-purple-400');
                dlStats.textContent = 'This may take quite a while...';
                bar.style.width = '75%';

                const dlRes = await fetch('/api/download/playlist', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({url: url, format_id: "best"})
                });

                if (!dlRes.ok) throw new Error("Bulk ZIP download failed.");

                const blob = await dlRes.blob();
                const blobUrl = window.URL.createObjectURL(blob);

                let filename = "playlist.zip";
                const disposition = dlRes.headers.get("content-disposition");
                if (disposition && disposition.includes("filename=")) {
                    filename = disposition.split("filename=")[1].replace(/"/g, '');
                }

                const a = document.createElement("a");
                a.href = blobUrl;
                a.download = filename;
                document.body.appendChild(a);
                a.click();
                a.remove();
                window.URL.revokeObjectURL(blobUrl);

                dlStatus.textContent = 'Playlist Downloaded!';
                dlStatus.classList.replace('text-purple-400', 'text-green-400');
                bar.style.width = '100%';
            }

        } catch (err) {
            dlStatus.innerText = 'Error: ' + err.message;
            dlStatus.classList.add('text-red-400');
            progressContainer.classList.remove('hidden');
            bar.style.width = '0%';
        } finally {
            btnText.textContent = 'Fetch & Download All';
            spinner.classList.add('hidden');
        }
    });
}