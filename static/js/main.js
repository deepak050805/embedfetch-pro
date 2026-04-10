// MVP Logic tracking Single and Playlist Downloader with Quality extraction

document.addEventListener('DOMContentLoaded', async () => {
    // Check FFmpeg status on load
    try {
        const res = await fetch('/api/system_status');
        const data = await res.json();
        if (!data.ffmpeg_installed) {
            const warnBox = document.getElementById('ffmpegWarning');
            if(warnBox) warnBox.classList.remove('hidden');
        }
    } catch(e) { console.error('Could not check system status'); }
});


// Step 1: Analyze Video
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
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url: url })
            });
            const data = await res.json();
            
            if (data.status === 'success') {
                // Clear out everything except the 'best' option
                const childrenArray = Array.from(formatsGrid.children);
                for(let i = 1; i < childrenArray.length; i++){
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

// Step 2: Download Selected Quality
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

        btnText.textContent = 'Requesting...';
        spinner.classList.remove('hidden');
        progressContainer.classList.remove('hidden');
        dlStatus.classList.remove('text-red-400', 'text-green-400');
        dlStatus.classList.add('text-purple-400');
        dlStatus.textContent = 'Starting...';

        try {
            const res = await fetch('/api/download/single', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url: url, format_id: formatId })
            });
            const data = await res.json();
            
            if (data.task_id) {
                pollProgress(data.task_id, dlStatus, dlStats, bar, btnText, spinner);
            }
        } catch (err) {
            dlStatus.textContent = 'Error initiating download';
            dlStatus.classList.replace('text-purple-400', 'text-red-400');
            btnText.textContent = 'Download Selected Format';
            spinner.classList.add('hidden');
        }
    });
}

// Playlist UI
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
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url: url })
            });
            const dataExt = await resExt.json();
            
            if (dataExt.status === 'success') {
                listContainer.classList.remove('hidden');
                listUl.innerHTML = dataExt.videos.map(v => 
                    `<li class="bg-dark-900/80 p-3 rounded-lg flex justify-between border border-white/5">
                        <span class="truncate font-medium text-gray-200">${v.title}</span>
                    </li>`
                ).join('');

                btnText.textContent = 'Starting Download...';
                
                const resDl = await fetch('/api/download/playlist', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ url: url, format_id: "best" })
                });
                const dataDl = await resDl.json();
                
                if (dataDl.task_id) {
                    progressContainer.classList.remove('hidden');
                    dlStatus.classList.remove('text-red-400', 'text-green-400');
                    dlStatus.classList.add('text-pink-400');
                    pollProgress(dataDl.task_id, dlStatus, dlStats, bar, btnText, spinner, true);
                }
            } else {
                throw new Error("Failed extraction");
            }
        } catch (err) {
            dlStatus.innerText = 'Error initiating playlist download';
            dlStatus.classList.replace('text-pink-400', 'text-red-400');
            btnText.textContent = 'Fetch & Download All';
            spinner.classList.add('hidden');
        }
    });
}

function pollProgress(taskId, statusEl, statsEl, barEl, btnText, spinner, isPlaylist = false) {
    const interval = setInterval(async () => {
        try {
            const res = await fetch(`/api/download_status/${taskId}`);
            const status = await res.json();
            
            if (status.status === 'error') {
                statusEl.textContent = 'Error: ' + status.error;
                if(isPlaylist) statusEl.classList.replace('text-pink-400', 'text-red-400');
                else statusEl.classList.replace('text-purple-400', 'text-red-400');
                clearInterval(interval);
                btnText.textContent = isPlaylist ? 'Fetch & Download All' : 'Start New Download';
                spinner.classList.add('hidden');
            } else {
                let percVal = parseFloat(status.progress) || 0;
                barEl.style.width = percVal + '%';
                
                statsEl.textContent = `${status.progress} | ${status.speed} | ETA: ${status.eta}`;
                statusEl.textContent = status.status.charAt(0).toUpperCase() + status.status.slice(1);
                
                if (status.status === 'completed') {
                    statusEl.textContent = 'Download Completed Successfully!';
                    barEl.style.width = '100%';
                    if(isPlaylist) statusEl.classList.replace('text-pink-400', 'text-green-400');
                    else statusEl.classList.replace('text-purple-400', 'text-green-400');
                    
                    clearInterval(interval);
                    btnText.textContent = 'Start New Download';
                    spinner.classList.add('hidden');
                }
            }
        } catch (e) {
            console.error(e);
        }
    }, 3000);
}
