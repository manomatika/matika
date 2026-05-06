document.addEventListener('DOMContentLoaded', () => {
    let selectedPageRow = null;
    let selectedSubjectRow = null;
    const permissionEditor = document.getElementById('permission-editor');
    const selectedPageDisplay = document.getElementById('selected-page-display');
    const formPagePath = document.getElementById('form-page-path');
    const subjectSelect = document.querySelector('select[name="subject"]');
    function updateEditor(path, label) {
        permissionEditor.style.display = 'block';
        selectedPageDisplay.textContent = `${label} (${path})`;
        formPagePath.value = path;
    }
    function selectPage(row, path, label) {
        if (selectedPageRow === row && !selectedSubjectRow) {
            // Deselect
            row.classList.remove('selected');
            selectedPageRow = null;
            permissionEditor.style.display = 'none';
        }
        else {
            // Select new page
            if (selectedPageRow)
                selectedPageRow.classList.remove('selected');
            if (selectedSubjectRow) {
                selectedSubjectRow.classList.remove('selected-row');
                selectedSubjectRow = null;
            }
            row.classList.add('selected');
            selectedPageRow = row;
            updateEditor(path, label);
            // Scroll into view if needed
            permissionEditor.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }
    }
    function selectSubject(row, subjectKey, pagePath, pageLabel) {
        // Find the page row
        const pageRow = row.closest('.page-row');
        if (!pageRow)
            return;
        // Visual highlight
        if (selectedSubjectRow)
            selectedSubjectRow.classList.remove('selected-row');
        if (selectedPageRow && selectedPageRow !== pageRow)
            selectedPageRow.classList.remove('selected');
        row.classList.add('selected-row');
        pageRow.classList.add('selected');
        selectedSubjectRow = row;
        selectedPageRow = pageRow;
        // Update form
        updateEditor(pagePath, pageLabel);
        subjectSelect.value = subjectKey;
        permissionEditor.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
    // Page row selection
    document.querySelectorAll('.page-row-header').forEach(header => {
        header.addEventListener('click', (e) => {
            const row = header.closest('.page-row');
            const path = row.getAttribute('data-page-path') || '';
            const label = row.getAttribute('data-page-label') || path;
            selectPage(row, path, label);
        });
    });
    // Subject row selection
    document.querySelectorAll('.subject-row').forEach(row => {
        row.addEventListener('click', (e) => {
            const target = e.target;
            if (target.closest('button') || target.closest('form'))
                return; // Ignore clicks on buttons/forms
            const pageRow = row.closest('.page-row');
            const subjectKey = row.getAttribute('data-subject-key') || '';
            const pagePath = row.getAttribute('data-page-path') || '';
            const pageLabel = pageRow ? (pageRow.getAttribute('data-page-label') || pagePath) : pagePath;
            selectSubject(row, subjectKey, pagePath, pageLabel);
        });
    });
});
export {};
