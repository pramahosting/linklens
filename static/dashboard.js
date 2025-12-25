document.addEventListener("DOMContentLoaded", () => {
    const form = document.querySelector('section.form-card form');
    const runBtn = document.getElementById('run-btn');
    const statusBox = document.getElementById('status-box');
    const resultsArea = document.getElementById('results-table-area');
    const scraperSelect = document.getElementById('scraper_mode');
    const fileInputContainer = document.getElementById('file_input_container');
    const fileInput = document.getElementById('input_excel');
    const resetBtn = document.getElementById('reset-btn');
    const scraperSpinner = document.getElementById('scraper-spinner');
    const progressContainer = document.getElementById('progress-container');

    // Debug: Check if spinner element exists
    console.log('Scraper Spinner Element:', scraperSpinner);

    // Make scraperRunning global for polling
    window.scraperRunning = false;
    window.resultsLoaded = false;

    // Check if scraper should be running on page load (after form submit)
    // Removed - not needed with AJAX submission

    function appendStatus(text) {
        if (!statusBox) return;
        const line = document.createElement('div');
        line.className = 'status-line';
        line.innerHTML = text;
        statusBox.appendChild(line);
        statusBox.scrollTop = statusBox.scrollHeight;
    }

    // Show spinner
    function showSpinner() {
        console.log('showSpinner called, scraperSpinner:', scraperSpinner);
        if (scraperSpinner) {
            scraperSpinner.style.display = 'flex';
            console.log('Spinner display set to flex');
        } else {
            console.error('scraperSpinner element not found!');
        }
    }

    // Hide spinner
    function hideSpinner() {
        if (scraperSpinner) {
            scraperSpinner.style.display = 'none';
        }
    }

    // Form submission
    if (form && runBtn && statusBox) {
        form.addEventListener('submit', (e) => {
            e.preventDefault(); // PREVENT PAGE RELOAD
            
            console.log('Form submitted - showing spinner');
            window.scraperRunning = true;
            runBtn.disabled = true;
            showSpinner();
            appendStatus('⏳ Scraper running...');
            
            // Submit form via AJAX to prevent page reload
            const formData = new FormData(form);
            
            fetch('/dashboard', {
                method: 'POST',
                body: formData
            })
            .then(response => {
                console.log('Form submitted successfully');
            })
            .catch(error => {
                console.error('Form submission error:', error);
                hideSpinner();
                runBtn.disabled = false;
            });
        });
    }

    // SSE status updates
    if (!!window.EventSource) {
        const source = new EventSource("/linkedin_status");

        source.onmessage = function (e) {
            const msg = e.data || '';

            if (msg.includes('RESULTS_READY')) {
                fetch("/get_results")
                    .then(r => r.json())
                    .then(j => {
                        renderResultsTable(j.results || []);
                        appendStatus('✅ Results loaded into table.');
                        window.scraperRunning = false;
                        hideSpinner();
                        runBtn.disabled = false;
                        window.resultsLoaded = true;
                    });
                return;
            }

            appendStatus(msg);

            // Show spinner when scraper starts
            if (msg.includes('🔍 Starting LinkedIn Scraper') ||
                msg.includes('🔐 Logging in') ||
                msg.includes('⏳ Scraper running')) {
                console.log('Detected scraper start message, showing spinner');
                if (!window.scraperRunning) {
                    window.scraperRunning = true;
                    showSpinner();
                    runBtn.disabled = true;
                }
            }

            // Hide spinner when scraper completes or errors
            if (msg.includes('✅ Scraping completed') || msg.startsWith('❌ Error:')) {
                console.log('Detected scraper end message, hiding spinner');
                window.scraperRunning = false;
                hideSpinner();
                runBtn.disabled = false;
            }
        };

        // Show spinner immediately if there's an open connection and scraper running
        source.addEventListener('open', function(e) {
            console.log('SSE connection opened');
        });
    }

    // Render results table
    function renderResultsTable(results) {
        if (!resultsArea) return;

        resultsArea.innerHTML = '';

        // Simple heading without download button
        const heading = document.createElement('h3');
        heading.textContent = 'Data Details';
        heading.style.marginTop = '0';
        heading.style.marginBottom = '8px';
        resultsArea.appendChild(heading);

        if (!results || results.length === 0) {
            const noResults = document.createElement('p');
            noResults.className = 'small';
            noResults.id = 'no-results';
            noResults.textContent = 'No results yet. Run the scraper to collect data.';
            resultsArea.appendChild(noResults);
            return;
        }

        const columnOrder = [
            '#', 'Name', 'Title', 'Company',
            'Location', 'Email', 'Phone', 'Skills', 'Experience', 'Source_URL'
        ];

        const wrapper = document.createElement('div');
        wrapper.className = 'table-responsive';

        const table = document.createElement('table');
        table.className = 'table';
        table.id = 'results-table';

        const thead = document.createElement('thead');
        const trh = document.createElement('tr');

        columnOrder.forEach(col => {
            const th = document.createElement('th');
            th.textContent = col;
            trh.appendChild(th);
        });

        thead.appendChild(trh);
        table.appendChild(thead);

        const tbody = document.createElement('tbody');

        results.forEach((row, index) => {
            const tr = document.createElement('tr');

            columnOrder.forEach(col => {
                const td = document.createElement('td');

                if (col === '#') {
                    td.textContent = index + 1;
                } else if (col === 'Skills' || col === 'Experience') {
                    const full = row[col] || '';
                    td.className = 'expandable-cell';
                    td.dataset.fullContent = full;
                    td.textContent = full.length > 30 ? full.slice(0, 30) + '...' : full;
                } else if (col === 'Source_URL') {
                    const a = document.createElement('a');
                    a.href = row[col] || '#';
                    a.target = '_blank';
                    a.textContent = 'View Profile';
                    td.appendChild(a);
                } else {
                    td.textContent = row[col] || '';
                }

                tr.appendChild(td);
            });

            tbody.appendChild(tr);
        });

        table.appendChild(tbody);
        wrapper.appendChild(table);
        resultsArea.appendChild(wrapper);

        // Add download button at bottom left (after table)
        const downloadBtn = document.createElement('a');
        downloadBtn.className = 'btn';
        downloadBtn.id = 'download-btn';
        downloadBtn.href = "/linkedin_download";
        downloadBtn.textContent = "Download Excel";
        downloadBtn.style.marginTop = '10px';
        downloadBtn.style.display = 'inline-block';
        downloadBtn.style.fontSize = '11px';
        downloadBtn.style.padding = '5px 10px';
        resultsArea.appendChild(downloadBtn);

        attachExpandableCellHandlers();
    }

    window.renderResultsTable = renderResultsTable;

    // Expandable modal handlers
    function attachExpandableCellHandlers() {
        const modal = document.getElementById('popup-modal');
        const modalTitle = document.getElementById('modal-title');
        const modalContent = document.getElementById('modal-content');
        const modalClose = document.getElementById('modal-close');
        if (!modal || !modalTitle || !modalContent || !modalClose) return;

        document.querySelectorAll('.expandable-cell').forEach(cell => {
            cell.addEventListener('click', function () {
                modalTitle.textContent =
                    this.cellIndex === 7 ? 'Skills' : 'Experience';
                modalContent.textContent =
                    this.dataset.fullContent || '';
                modal.style.display = 'flex';
            });
        });

        modalClose.onclick = () => modal.style.display = 'none';
        modal.onclick = e => {
            if (e.target === modal) modal.style.display = 'none';
        };
    }

    // File input toggle
    function toggleFileInput() {
        if (!scraperSelect || !fileInputContainer) return;
        const v = scraperSelect.value;
        fileInputContainer.style.display =
            (v === 'html_only' || v === 'html_and_data') ? 'block' : 'none';
    }

    toggleFileInput();
    scraperSelect?.addEventListener('change', toggleFileInput);

    // FIXED RESET BUTTON - Use event listener instead of inline onclick
    if (resetBtn && form) {
        resetBtn.addEventListener("click", (e) => {
            e.preventDefault();
            
            // Reset form fields
            form.reset();
            
            // Clear file input
            if (fileInput) fileInput.value = "";
            
            // Hide file input container
            if (fileInputContainer) fileInputContainer.style.display = "none";

            // Reset global flags
            window.scraperRunning = false;
            window.resultsLoaded = false;

            // Reset UI elements
            hideSpinner();
            if (runBtn) runBtn.disabled = false;
            
            // Clear status box
            if (statusBox) {
                statusBox.innerHTML = '<div class="status-line">Ready</div>';
            }
            
            // Hide and reset progress bar
            if (progressContainer) {
                progressContainer.style.display = 'none';
                const progressBar = document.getElementById('progress-bar');
                const progressCount = document.getElementById('progress-count');
                if (progressBar) progressBar.style.width = '0%';
                if (progressCount) progressCount.textContent = '0 / 0';
            }
            
            // Clear results area
            if (resultsArea) {
                resultsArea.innerHTML =
                    '<h3 style="margin-top:0;">Data Details</h3>' +
                    '<p class="small" id="no-results">No results yet. Run the scraper to collect data.</p>';
            }

            // Reset max results slider display
            const maxResultsValue = document.getElementById('max-results-value');
            const maxResultsSlider = document.getElementById('max_results');
            if (maxResultsValue && maxResultsSlider) {
                maxResultsValue.textContent = maxResultsSlider.value;
            }

            console.log("✅ Form reset completed");
        });
    }
});

// Polling for results (optional)
let resultsLoaded = false;

async function pollResults() {
    if (resultsLoaded || window.scraperRunning) return;

    try {
        const res = await fetch("/get_results");
        const data = await res.json();

        if (data.results && data.results.length > 0) {
            resultsLoaded = true;
            if (typeof window.renderResultsTable === 'function') {
                window.renderResultsTable(data.results);
            }
        }
    } catch (e) {
        console.error("Polling failed", e);
    }
}

// Uncomment to enable polling
// setInterval(pollResults, 2000);