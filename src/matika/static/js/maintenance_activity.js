var __awaiter = (this && this.__awaiter) || function (thisArg, _arguments, P, generator) {
    function adopt(value) { return value instanceof P ? value : new P(function (resolve) { resolve(value); }); }
    return new (P || (P = Promise))(function (resolve, reject) {
        function fulfilled(value) { try { step(generator.next(value)); } catch (e) { reject(e); } }
        function rejected(value) { try { step(generator["throw"](value)); } catch (e) { reject(e); } }
        function step(result) { result.done ? resolve(result.value) : adopt(result.value).then(fulfilled, rejected); }
        step((generator = generator.apply(thisArg, _arguments || [])).next());
    });
};
export class MaintenanceActivityManager {
    constructor(metadata) {
        this.metadata = metadata;
        this.selectedRow = null;
        this.isEditing = false;
        this.isNew = false;
        this.originalData = {};
        this.btnNew = document.getElementById('btn-new');
        this.btnEdit = document.getElementById('btn-edit');
        this.btnDelete = document.getElementById('btn-delete');
        this.btnSave = document.getElementById('btn-save');
        this.btnCancel = document.getElementById('btn-cancel');
        this.btnSearch = document.getElementById('btn-search');
        this.searchInput = document.getElementById('search-input');
        this.searchField = document.getElementById('search-field');
        this.maintenanceForm = document.getElementById('maintenance-form');
        this.actionForm = document.getElementById('action-form');
        this.sep = document.getElementById('status-error-panel');
        this.sepContent = document.getElementById('sep-content');
        this.initEventListeners();
        this.disableForm();
        this.updateButtonStates();
    }
    initEventListeners() {
        var _a, _b, _c, _d, _e, _f, _g, _h;
        // BT Selection
        const tableBody = document.querySelector('#browse-table tbody');
        tableBody === null || tableBody === void 0 ? void 0 : tableBody.addEventListener('click', (e) => {
            const tr = e.target.closest('tr');
            if (tr && tableBody.contains(tr)) {
                this.selectRow(tr);
            }
        });
        // AP Buttons
        (_a = this.btnNew) === null || _a === void 0 ? void 0 : _a.addEventListener('click', () => this.handleNew());
        (_b = this.btnEdit) === null || _b === void 0 ? void 0 : _b.addEventListener('click', () => this.handleEdit());
        (_c = this.btnDelete) === null || _c === void 0 ? void 0 : _c.addEventListener('click', () => this.handleDelete());
        // SP Buttons
        (_d = this.btnSave) === null || _d === void 0 ? void 0 : _d.addEventListener('click', () => this.handleSave());
        (_e = this.btnCancel) === null || _e === void 0 ? void 0 : _e.addEventListener('click', () => this.handleCancel());
        // Search Button
        (_f = this.btnSearch) === null || _f === void 0 ? void 0 : _f.addEventListener('click', () => {
            this.filterTable(this.searchField.value, this.searchInput.value);
        });
        // Form Dirty Checking
        (_g = this.maintenanceForm) === null || _g === void 0 ? void 0 : _g.addEventListener('input', () => this.checkDirty());
        (_h = this.maintenanceForm) === null || _h === void 0 ? void 0 : _h.addEventListener('change', () => this.checkDirty());
    }
    showMessage(msg, isError = false) {
        if (this.sepContent && this.sep) {
            this.sepContent.textContent = msg;
            this.sepContent.style.color = isError ? '#c00' : '#28a745';
            this.sep.style.display = 'block';
        }
    }
    clearMessage() {
        if (this.sepContent && this.sep) {
            this.sepContent.textContent = '';
            this.sep.style.display = 'none';
        }
    }
    selectRow(row) {
        if (this.selectedRow === row)
            return;
        if (this.isDirty()) {
            if (!confirm("Discard unsaved changes?"))
                return;
        }
        if (this.selectedRow)
            this.selectedRow.classList.remove('selected');
        this.selectedRow = row;
        this.selectedRow.classList.add('selected');
        this.isEditing = false;
        this.isNew = false;
        this.populateFormFromRow(row);
        this.disableForm();
        this.updateButtonStates();
        this.clearMessage();
    }
    populateFormFromRow(row) {
        this.originalData = {};
        this.metadata.maintenance_panel.fields.forEach(f => {
            const val = row.getAttribute(`data-${f.name.replace(/_/g, '-')}`) || '';
            const input = document.getElementById(`field-${f.name}`);
            if (input) {
                // Internal percentage formatting
                if (f.suffix === '%' && val) {
                    const num = parseFloat(val);
                    if (!isNaN(num)) {
                        // Convert decimal (0.05) to percentage (5.00%)
                        input.value = (num * 100).toFixed(2) + '%';
                    }
                    else {
                        input.value = val;
                    }
                }
                else {
                    input.value = val;
                }
                this.originalData[f.name] = val;
            }
        });
    }
    disableForm() {
        const inputs = this.maintenanceForm.querySelectorAll('input, select');
        inputs.forEach(i => i.disabled = true);
        const lookupButtons = this.maintenanceForm.querySelectorAll('.btn-lookup');
        lookupButtons.forEach(btn => btn.style.display = 'none');
        // Show refresh buttons in read mode if a row is selected
        const refreshButtons = this.maintenanceForm.querySelectorAll('.btn-refresh-field');
        refreshButtons.forEach(btn => {
            btn.style.display = this.selectedRow ? 'inline-block' : 'none';
        });
    }
    enableForm() {
        this.metadata.maintenance_panel.fields.forEach(f => {
            const input = document.getElementById(`field-${f.name}`);
            if (input) {
                input.disabled = f.read_only;
            }
        });
        const lookupButtons = this.maintenanceForm.querySelectorAll('.btn-lookup');
        lookupButtons.forEach(btn => btn.style.display = 'inline-block');
        // Hide refresh buttons in edit/new mode
        const refreshButtons = this.maintenanceForm.querySelectorAll('.btn-refresh-field');
        refreshButtons.forEach(btn => btn.style.display = 'none');
    }
    updateButtonStates() {
        if (this.btnNew)
            this.btnNew.disabled = false;
        const canEdit = this.selectedRow && !this.isNew && !this.isEditing;
        const canDelete = this.selectedRow && !this.isNew;
        if (this.btnEdit)
            this.btnEdit.disabled = !canEdit;
        if (this.btnDelete)
            this.btnDelete.disabled = !canDelete;
        this.checkDirty();
    }
    isDirty() {
        if (this.isNew)
            return true;
        if (!this.isEditing)
            return false;
        return this.metadata.maintenance_panel.fields.some(f => {
            const input = document.getElementById(`field-${f.name}`);
            if (!input)
                return false;
            let currentVal = input.value;
            // Strip % and convert back to decimal for comparison
            if (f.suffix === '%' && currentVal.endsWith('%')) {
                const num = parseFloat(currentVal.replace('%', ''));
                if (!isNaN(num)) {
                    currentVal = (num / 100).toString();
                }
            }
            // Normalize for comparison
            const orig = this.originalData[f.name] || '';
            if (f.suffix === '%' && currentVal && orig) {
                return parseFloat(currentVal).toFixed(6) !== parseFloat(orig).toFixed(6);
            }
            return currentVal !== orig;
        });
    }
    checkDirty() {
        const dirty = this.isDirty();
        if (this.btnSave)
            this.btnSave.disabled = !dirty;
        if (this.btnCancel)
            this.btnCancel.disabled = !dirty;
    }
    handleNew() {
        if (this.isDirty() && !confirm("Discard unsaved changes?"))
            return;
        this.isNew = true;
        this.isEditing = false;
        if (this.selectedRow)
            this.selectedRow.classList.remove('selected');
        this.selectedRow = null;
        this.metadata.maintenance_panel.fields.forEach(f => {
            const input = document.getElementById(`field-${f.name}`);
            if (input)
                input.value = '';
        });
        this.enableForm();
        this.updateButtonStates();
        this.clearMessage();
    }
    handleEdit() {
        if (!this.selectedRow)
            return;
        this.isEditing = true;
        this.enableForm();
        this.updateButtonStates();
    }
    handleCancel() {
        this.isNew = false;
        this.isEditing = false;
        if (this.selectedRow) {
            this.populateFormFromRow(this.selectedRow);
        }
        else {
            this.maintenanceForm.querySelectorAll('input, select').forEach(i => i.value = '');
        }
        this.disableForm();
        this.updateButtonStates();
        this.clearMessage();
    }
    handleSave() {
        return __awaiter(this, void 0, void 0, function* () {
            if (!this.isNew && !this.selectedRow)
                return;
            const url = this.isNew ? this.getCreateUrl() : this.getUpdateUrl(this.selectedRow.getAttribute('data-id'));
            const formData = new URLSearchParams();
            this.metadata.maintenance_panel.fields.forEach(f => {
                const input = document.getElementById(`field-${f.name}`);
                if (input) {
                    let val = input.value;
                    // Strip % and convert to decimal for submission
                    if (f.suffix === '%' && val.endsWith('%')) {
                        const num = parseFloat(val.replace('%', ''));
                        if (!isNaN(num)) {
                            val = (num / 100).toString();
                        }
                    }
                    formData.append(f.name, val);
                }
            });
            try {
                this.clearMessage();
                const resp = yield fetch(url, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                    body: formData
                });
                if (resp.ok) {
                    window.location.reload();
                }
                else {
                    const data = yield resp.json();
                    this.showMessage(data.detail || "Save failed", true);
                }
            }
            catch (err) {
                this.showMessage(err.message || "An error occurred during save", true);
            }
        });
    }
    handleDelete() {
        return __awaiter(this, void 0, void 0, function* () {
            if (this.isDirty() && !confirm("Discard unsaved changes?"))
                return;
            if (!this.selectedRow || !confirm("Are you sure you want to delete this record?"))
                return;
            const url = this.getDeleteUrl(this.selectedRow.getAttribute('data-id'));
            try {
                this.clearMessage();
                const resp = yield fetch(url, { method: 'POST' });
                if (resp.ok) {
                    window.location.reload();
                }
                else {
                    const data = yield resp.json();
                    this.showMessage(data.detail || "Delete failed", true);
                }
            }
            catch (err) {
                this.showMessage(err.message || "An error occurred during delete", true);
            }
        });
    }
    filterTable(field, query) {
        const rows = document.querySelectorAll('#browse-table tbody tr');
        const q = query.toLowerCase();
        // Find which column index matches 'field'
        const columns = this.metadata.browse_panel.columns;
        const colIndex = columns.findIndex(c => c.name === field);
        rows.forEach(row => {
            var _a;
            if (!q) {
                row.style.display = '';
                return;
            }
            if (colIndex === -1)
                return;
            const cell = row.cells[colIndex];
            if (cell) {
                const text = ((_a = cell.textContent) === null || _a === void 0 ? void 0 : _a.toLowerCase()) || '';
                row.style.display = text.includes(q) ? '' : 'none';
            }
        });
    }
    getCreateUrl() { return ""; }
    getUpdateUrl(id) { return ""; }
    getDeleteUrl(id) { return ""; }
}
