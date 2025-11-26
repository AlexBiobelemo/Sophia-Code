(() => {
    const selectAllCheckbox = document.getElementById('select-all-snippets');
    const bulkActionsDropdown = document.getElementById('bulk-actions-dropdown');
    const bulkDeleteBtn = document.getElementById('bulk-delete-btn');
    const bulkCopyBtn = document.getElementById('bulk-copy-btn');
    const bulkMoveBtn = document.getElementById('bulk-move-btn');
    const confirmBulkActionBtn = document.getElementById('confirm-bulk-action-btn');
    const bulkCopyMovePanel = document.getElementById('bulkCopyMovePanel');
    const bulkCopyMovePanelClose = document.getElementById('bulkCopyMovePanelClose');
    const modalBackdrop = document.getElementById('modalBackdrop');

    const updateBulkActionsState = () => {
        const checkedCount = document.querySelectorAll('.snippet-checkbox:checked').length;
        if (bulkActionsDropdown) {
            bulkActionsDropdown.disabled = checkedCount === 0;
        }
    };

    const updateBulkActionsStateAndSelectAll = () => {
        updateBulkActionsState();
        const currentSnippetCheckboxes = document.querySelectorAll('.snippet-checkbox');
        const allChecked = currentSnippetCheckboxes.length > 0 && Array.from(currentSnippetCheckboxes).every(cb => cb.checked);
        if (selectAllCheckbox) {
            selectAllCheckbox.checked = allChecked;
        }
    };

    const attachSnippetCheckboxListeners = () => {
        document.querySelectorAll('.snippet-checkbox').forEach(checkbox => {
            // Remove existing listener to prevent duplicates
            checkbox.removeEventListener('change', updateBulkActionsStateAndSelectAll);
            checkbox.addEventListener('change', updateBulkActionsStateAndSelectAll);
        });
    };

    // Initial attachment of listeners for snippets present on page load
    attachSnippetCheckboxListeners();

    if (selectAllCheckbox) {
        selectAllCheckbox.addEventListener('change', () => {
            document.querySelectorAll('.snippet-checkbox').forEach(checkbox => {
                checkbox.checked = selectAllCheckbox.checked;
            });
            updateBulkActionsState();
        });
    }

    const getSelectedSnippetIds = () => {
        return Array.from(document.querySelectorAll('.snippet-checkbox:checked')).map(cb => cb.value);
    };

    if (bulkDeleteBtn) {
        bulkDeleteBtn.addEventListener('click', () => {
            const ids = getSelectedSnippetIds();
            if (ids.length === 0) {
                alert('Please select at least one snippet.');
                return;
            }
            if (confirm(`Delete ${ids.length} snippet(s)? This action cannot be undone.`)) {
                const form = document.getElementById('bulk-actions-form');
                Array.from(form.querySelectorAll('input[type="hidden"][name="action"], input[type="hidden"][name="target_collection"], input[type="hidden"][name="snippet_ids"]'))
                     .forEach(input => input.remove());
                
                const input = document.createElement('input');
                input.type = 'hidden';
                input.name = 'snippet_ids';
                input.value = ids.join(',');
                form.appendChild(input);
                
                const actionInput = document.createElement('input');
                actionInput.type = 'hidden';
                actionInput.name = 'action';
                actionInput.value = 'delete';
                form.appendChild(actionInput);
                
                form.action = window.SOPHIA_CONFIG.bulkDeleteUrl;
                form.submit();
            }
        });
    }

    const openBulkCopyMovePanel = (action) => {
        if (!bulkCopyMovePanel) return;
        const ids = getSelectedSnippetIds();
        if (ids.length === 0) {
            alert('Please select at least one snippet.');
            return;
        }
        document.getElementById('bulk-snippet-ids').value = ids.join(',');
        document.getElementById('bulk-action-type').value = action;
        bulkCopyMovePanel.style.display = 'block';
        if (modalBackdrop) modalBackdrop.style.display = 'block';
    };

    if (bulkCopyBtn) {
        bulkCopyBtn.addEventListener('click', () => openBulkCopyMovePanel(bulkCopyBtn.dataset.action));
    }

    if (bulkMoveBtn) {
        bulkMoveBtn.addEventListener('click', () => openBulkCopyMovePanel(bulkMoveBtn.dataset.action));
    }

    if (bulkCopyMovePanelClose) {
        bulkCopyMovePanelClose.addEventListener('click', () => {
            bulkCopyMovePanel.style.display = 'none';
            if (modalBackdrop) modalBackdrop.style.display = 'none';
        });
    }

    if (confirmBulkActionBtn) {
        confirmBulkActionBtn.addEventListener('click', (e) => {
            e.preventDefault();
            const action = document.getElementById('bulk-action-type').value;
            const targetCollection = document.getElementById('target_collection').value;
            const snippetIds = document.getElementById('bulk-snippet-ids').value;

            if (!targetCollection || targetCollection === '0') {
                alert('Please select a target collection.');
                return;
            }

            const bulkForm = document.getElementById('bulk-actions-form');
            Array.from(bulkForm.querySelectorAll('input[type="hidden"][name="action"], input[type="hidden"][name="target_collection"], input[type="hidden"][name="snippet_ids"]'))
                 .forEach(input => input.remove());

            const actionInput = document.createElement('input');
            actionInput.type = 'hidden';
            actionInput.name = 'action';
            actionInput.value = action;
            bulkForm.appendChild(actionInput);

            const collectionInput = document.createElement('input');
            collectionInput.type = 'hidden';
            collectionInput.name = 'target_collection';
            collectionInput.value = targetCollection;
            bulkForm.appendChild(collectionInput);

            const idsInput = document.createElement('input');
            idsInput.type = 'hidden';
            idsInput.name = 'snippet_ids';
            idsInput.value = snippetIds;
            bulkForm.appendChild(idsInput);

            bulkForm.action = window.SOPHIA_CONFIG.bulkCopyMoveUrl;
            bulkForm.submit();

            if (bulkCopyMovePanel) {
                bulkCopyMovePanel.style.display = 'none';
                if (modalBackdrop) modalBackdrop.style.display = 'none';
            }
        });
    }

    updateBulkActionsState();

    // Tags dropdown: typeahead-style fetch without external dependencies
    (() => {
        const searchInput = document.getElementById('tag-search');
        const clearBtn = document.getElementById('tag-clear');
        const results = document.getElementById('tag-results');
        if (!searchInput || !results) return;

        let controller = null;
        const render = (tags) => {
            results.innerHTML = '';
            if (!tags || !tags.length) {
                results.innerHTML = '<div class="text-muted small">No tags</div>';
                return;
            }
            tags.forEach(tag => {
                const a = document.createElement('a');
                a.className = 'list-group-item list-group-item-action';
                a.textContent = tag;
                a.href = `${window.SOPHIA_CONFIG.indexUrl}?tag=${encodeURIComponent(tag)}&language=${encodeURIComponent(window.SOPHIA_CONFIG.selectedLanguage)}&sort=${encodeURIComponent(window.SOPHIA_CONFIG.selectedSort)}&q=${encodeURIComponent(window.SOPHIA_CONFIG.textQuery)}`;
                results.appendChild(a);
            });
        };
        const fetchTags = async (q) => {
            try {
                if (controller) controller.abort();
                controller = new AbortController();
                const res = await fetch(`${window.SOPHIA_CONFIG.apiTagsUrl}?q=${encodeURIComponent(q||'')}&limit=50`, { signal: controller.signal });
                const data = await res.json();
                render(data.tags || []);
            } catch (e) { /* ignore aborts */ }
        };
        searchInput.addEventListener('input', () => fetchTags(searchInput.value.trim()));
        clearBtn?.addEventListener('click', () => { searchInput.value=''; fetchTags(''); });
        fetchTags('');
    })();

    // Infinite scroll (progressive enhancement). Falls back to pagination if not supported.
    (() => {
        const container = document.getElementById('snippets-container');
        const sentinel = document.getElementById('scroll-sentinel');
        if (!container || !sentinel || !('IntersectionObserver' in window)) return;
        let nextPage = window.SOPHIA_CONFIG.snippetsNextNum;
        const buildNextUrl = () => {
            if (!nextPage) return null;
            const params = new URLSearchParams();
            params.append('page', nextPage);
            params.append('partial', '1');
            if (window.SOPHIA_CONFIG.selectedLanguage) params.append('language', window.SOPHIA_CONFIG.selectedLanguage);
            if (window.SOPHIA_CONFIG.selectedTag) params.append('tag', window.SOPHIA_CONFIG.selectedTag);
            if (window.SOPHIA_CONFIG.selectedSort) params.append('sort', window.SOPHIA_CONFIG.selectedSort);
            if (window.SOPHIA_CONFIG.textQuery) params.append('q', window.SOPHIA_CONFIG.textQuery);
            return `${window.SOPHIA_CONFIG.indexUrl}?${params.toString()}`;
        };
        let loading = false;

        const io = new IntersectionObserver(async (entries) => {
            if (!entries[0].isIntersecting || loading) return;
            const url = buildNextUrl();
            if (!url) { sentinel.textContent = 'No more items.'; io.disconnect(); return; }
            loading = true;
            try {
                const res = await fetch(url, { credentials: 'same-origin' });
                const html = await res.text();
                if (html.trim()) {
                    const tmp = document.createElement('div');
                    tmp.innerHTML = html;
                    container.append(...tmp.children);
                    nextPage = (nextPage || 1) + 1;
                    attachSnippetCheckboxListeners(); // Re-attach listeners after new content is loaded
                } else {
                    io.disconnect();
                    sentinel.textContent = 'No more items.';
                }
            } catch (e) {
                io.disconnect();
            } finally {
                loading = false;
            }
        }, { rootMargin: '200px' });
        io.observe(sentinel);
        const pag = document.querySelector('nav[aria-label="Snippet navigation"]');
        if (pag) pag.style.display = 'none';
    })();

})();
