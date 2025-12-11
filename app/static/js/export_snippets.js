document.addEventListener('DOMContentLoaded', function() {
    const dlAllBtn = document.getElementById('download-all-btn');
    const allSort = document.getElementById('all-sort');
    const dlColBtn = document.getElementById('download-collections-btn');
    const colSort = document.getElementById('col-sort');
    const includeSub = document.getElementById('include-sub');
    const collectionsSel = document.getElementById('collections-select');

    // Individual snippet export elements
    const selectAllSnippetsCheckbox = document.getElementById('select-all-snippets');
    const individualSnippetsList = document.getElementById('individual-snippets-list');
    const downloadSelectedSnippetsBtn = document.getElementById('download-selected-snippets-btn');
    const individualSort = document.getElementById('individual-sort');

    // --- Existing functionality (All Snippets & Collections) ---
    dlAllBtn.addEventListener('click', function() {
        const sort = allSort.value;
        window.location.href = `/export/download?sort=${encodeURIComponent(sort)}`;
    });

    dlColBtn.addEventListener('click', function() {
        const selected = Array.from(collectionsSel.selectedOptions).map(o => o.value).filter(Boolean);
        if (!selected.length) {
            alert('Please select at least one collection.');
            return;
        }
        const sort = colSort.value;
        const qs = new URLSearchParams({
            collections: selected.join(','),
            include_sub: includeSub.checked ? '1' : '0',
            sort,
        });
        window.location.href = `/export/download?${qs.toString()}`;
    });

    // --- New functionality (Individual Snippets) ---
    let allSnippets = []; // To store all snippets fetched from the API

    const fetchAllSnippets = async () => {
        individualSnippetsList.innerHTML = '<p class="text-muted text-center">Loading snippets...</p>';
        try {
            const response = await fetch(window.SOPHIA_EXPORT_CONFIG.apiExportSnippetsUrl);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            allSnippets = await response.json();
            renderIndividualSnippets();
        } catch (error) {
            console.error("Error fetching snippets:", error);
            individualSnippetsList.innerHTML = '<p class="text-danger text-center">Failed to load snippets.</p>';
        }
    };

    const renderIndividualSnippets = () => {
        individualSnippetsList.innerHTML = ''; // Clear previous content

        if (allSnippets.length === 0) {
            individualSnippetsList.innerHTML = '<p class="text-muted text-center">No snippets available.</p>';
            downloadSelectedSnippetsBtn.disabled = true;
            selectAllSnippetsCheckbox.disabled = true;
            return;
        }

        // Apply sorting
        const sort = individualSort.value;
        const sortedSnippets = [...allSnippets].sort((a, b) => {
            if (sort === 'alpha') {
                return a.title.localeCompare(b.title);
            } else if (sort === 'date_asc') {
                return new Date(a.timestamp) - new Date(b.timestamp);
            } else { // date_desc
                return new Date(b.timestamp) - new Date(a.timestamp);
            }
        });

        sortedSnippets.forEach(snippet => {
            const div = document.createElement('div');
            div.className = 'form-check';
            div.innerHTML = `
                <input class="form-check-input snippet-checkbox" type="checkbox" value="${snippet.id}" id="snippet-${snippet.id}">
                <label class="form-check-label" for="snippet-${snippet.id}">
                    ${snippet.title} <span class="text-muted small">(${snippet.language})</span>
                </label>
            `;
            individualSnippetsList.appendChild(div);
        });

        attachIndividualCheckboxListeners();
        updateDownloadButtonState();
        selectAllSnippetsCheckbox.disabled = false;
        updateSelectAllCheckboxState(); // Update select-all if snippets are re-rendered
    };

    const attachIndividualCheckboxListeners = () => {
        document.querySelectorAll('.snippet-checkbox').forEach(checkbox => {
            checkbox.addEventListener('change', () => {
                updateDownloadButtonState();
                updateSelectAllCheckboxState();
            });
        });
    };

    const updateDownloadButtonState = () => {
        const checkedCount = document.querySelectorAll('.snippet-checkbox:checked').length;
        downloadSelectedSnippetsBtn.disabled = checkedCount === 0;
    };

    const updateSelectAllCheckboxState = () => {
        const allCheckboxes = document.querySelectorAll('.snippet-checkbox');
        const checkedCheckboxes = document.querySelectorAll('.snippet-checkbox:checked');
        selectAllSnippetsCheckbox.checked = allCheckboxes.length > 0 && checkedCheckboxes.length === allCheckboxes.length;
    };

    if (selectAllSnippetsCheckbox) {
        selectAllSnippetsCheckbox.addEventListener('change', () => {
            document.querySelectorAll('.snippet-checkbox').forEach(checkbox => {
                checkbox.checked = selectAllSnippetsCheckbox.checked;
            });
            updateDownloadButtonState();
        });
    }

    if (individualSort) {
        individualSort.addEventListener('change', renderIndividualSnippets);
    }

    if (downloadSelectedSnippetsBtn) {
        downloadSelectedSnippetsBtn.addEventListener('click', function() {
            const selectedSnippetIds = Array.from(document.querySelectorAll('.snippet-checkbox:checked'))
                                            .map(cb => cb.value);
            if (selectedSnippetIds.length === 0) {
                alert('Please select at least one snippet to export.');
                return;
            }

            const sort = individualSort.value;
            const qs = new URLSearchParams({
                ids: selectedSnippetIds.join(','),
                sort: sort,
            });
            window.location.href = `${window.SOPHIA_EXPORT_CONFIG.exportSelectedZipUrl}?${qs.toString()}`;
        });
    }

    // Initial load
    fetchAllSnippets();
});