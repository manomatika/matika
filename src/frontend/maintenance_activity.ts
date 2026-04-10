export interface ActivityMetadata {
    browse_panel: {
        search_fields?: Array<{ name: string; label_key: string }>;
        columns: Array<{ name: string; label_key: string }>;
    };
    maintenance_panel: {
        buttons: string[];
        fields: Array<{
            name: string;
            label_key: string;
            read_only: boolean;
            required?: boolean;
            type?: string;
            options_source?: string;
            has_lookup?: boolean;
            suffix?: string;
        }>;
    };
}

export class MaintenanceActivityManager {
    protected selectedRow: HTMLElement | null = null;
    protected isEditing = false;
    protected isNew = false;
    protected originalData: Record<string, string> = {};

    protected btnNew = document.getElementById('btn-new') as HTMLButtonElement;
    protected btnEdit = document.getElementById('btn-edit') as HTMLButtonElement;
    protected btnDelete = document.getElementById('btn-delete') as HTMLButtonElement;
    protected btnSave = document.getElementById('btn-save') as HTMLButtonElement;
    protected btnCancel = document.getElementById('btn-cancel') as HTMLButtonElement;
    protected btnSearch = document.getElementById('btn-search') as HTMLButtonElement;
    protected searchInput = document.getElementById('search-input') as HTMLInputElement;
    protected searchField = document.getElementById('search-field') as HTMLSelectElement;
    
    protected maintenanceForm = document.getElementById('maintenance-form') as HTMLElement;
    protected actionForm = document.getElementById('action-form') as HTMLFormElement;
    protected sep = document.getElementById('status-error-panel') as HTMLElement;
    protected sepContent = document.getElementById('sep-content') as HTMLElement;

    constructor(protected metadata: ActivityMetadata) {
        this.initEventListeners();
        this.disableForm();
        this.updateButtonStates();
    }

    private initEventListeners() {
        // BT Selection
        const tableBody = document.querySelector('#browse-table tbody');
        tableBody?.addEventListener('click', (e) => {
            const tr = (e.target as HTMLElement).closest('tr');
            if (tr && tableBody.contains(tr)) {
                this.selectRow(tr as HTMLElement);
            }
        });

        // AP Buttons
        this.btnNew?.addEventListener('click', () => this.handleNew());
        this.btnEdit?.addEventListener('click', () => this.handleEdit());
        this.btnDelete?.addEventListener('click', () => this.handleDelete());

        // SP Buttons
        this.btnSave?.addEventListener('click', () => this.handleSave());
        this.btnCancel?.addEventListener('click', () => this.handleCancel());

        // Search Button
        this.btnSearch?.addEventListener('click', () => {
            this.filterTable(this.searchField.value, this.searchInput.value);
        });

        // Form Dirty Checking
        this.maintenanceForm?.addEventListener('input', () => this.checkDirty());
        this.maintenanceForm?.addEventListener('change', () => this.checkDirty());
    }

    protected showMessage(msg: string, isError: boolean = false) {
        if (this.sepContent && this.sep) {
            this.sepContent.textContent = msg;
            this.sepContent.style.color = isError ? '#c00' : '#28a745';
            this.sep.style.display = 'block';
        }
    }

    protected clearMessage() {
        if (this.sepContent && this.sep) {
            this.sepContent.textContent = '';
            this.sep.style.display = 'none';
        }
    }

    protected selectRow(row: HTMLElement) {
        if (this.selectedRow === row) return;
        
        if (this.isDirty()) {
            if (!confirm("Discard unsaved changes?")) return;
        }

        if (this.selectedRow) this.selectedRow.classList.remove('selected');
        this.selectedRow = row;
        this.selectedRow.classList.add('selected');

        this.isEditing = false;
        this.isNew = false;
        
        this.populateFormFromRow(row);
        this.disableForm();
        this.updateButtonStates();
        this.clearMessage();
    }

    protected populateFormFromRow(row: HTMLElement) {
        this.originalData = {};
        this.metadata.maintenance_panel.fields.forEach(f => {
            const val = row.getAttribute(`data-${f.name.replace(/_/g, '-')}`) || '';
            const input = document.getElementById(`field-${f.name}`) as HTMLInputElement | HTMLSelectElement;
            if (input) {
                // Internal percentage formatting
                if (f.suffix === '%' && val) {
                    const num = parseFloat(val);
                    if (!isNaN(num)) {
                        // Convert decimal (0.05) to percentage (5.00%)
                        input.value = (num * 100).toFixed(2) + '%';
                    } else {
                        input.value = val;
                    }
                } else {
                    input.value = val;
                }
                this.originalData[f.name] = val;
            }
        });
    }

    protected disableForm() {
        const inputs = this.maintenanceForm.querySelectorAll('input, select');
        inputs.forEach(i => (i as HTMLInputElement).disabled = true);
        const lookupButtons = this.maintenanceForm.querySelectorAll('.btn-lookup');
        lookupButtons.forEach(btn => (btn as HTMLElement).style.display = 'none');
        
        // Show refresh buttons in read mode if a row is selected
        const refreshButtons = this.maintenanceForm.querySelectorAll('.btn-refresh-field');
        refreshButtons.forEach(btn => {
            (btn as HTMLElement).style.display = this.selectedRow ? 'inline-block' : 'none';
        });
    }

    protected enableForm() {
        this.metadata.maintenance_panel.fields.forEach(f => {
            const input = document.getElementById(`field-${f.name}`) as HTMLInputElement | HTMLSelectElement;
            if (input) {
                input.disabled = f.read_only;
            }
        });
        const lookupButtons = this.maintenanceForm.querySelectorAll('.btn-lookup');
        lookupButtons.forEach(btn => (btn as HTMLElement).style.display = 'inline-block');
        
        // Hide refresh buttons in edit/new mode
        const refreshButtons = this.maintenanceForm.querySelectorAll('.btn-refresh-field');
        refreshButtons.forEach(btn => (btn as HTMLElement).style.display = 'none');
    }

    protected updateButtonStates() {
        if (this.btnNew) this.btnNew.disabled = false;

        const canEdit = this.selectedRow && !this.isNew && !this.isEditing;
        const canDelete = this.selectedRow && !this.isNew; 
        
        if (this.btnEdit) this.btnEdit.disabled = !canEdit;
        if (this.btnDelete) this.btnDelete.disabled = !canDelete;
        
        this.checkDirty();
    }

    protected isDirty(): boolean {
        if (this.isNew) return true;
        if (!this.isEditing) return false;

        return this.metadata.maintenance_panel.fields.some(f => {
            const input = document.getElementById(`field-${f.name}`) as HTMLInputElement | HTMLSelectElement;
            if (!input) return false;
            
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

    protected checkDirty() {
        const dirty = this.isDirty();
        if (this.btnSave) this.btnSave.disabled = !dirty;
        if (this.btnCancel) this.btnCancel.disabled = !dirty;
    }

    protected handleNew() {
        if (this.isDirty() && !confirm("Discard unsaved changes?")) return;

        this.isNew = true;
        this.isEditing = false;
        if (this.selectedRow) this.selectedRow.classList.remove('selected');
        this.selectedRow = null;

        this.metadata.maintenance_panel.fields.forEach(f => {
            const input = document.getElementById(`field-${f.name}`) as HTMLInputElement | HTMLSelectElement;
            if (input) input.value = '';
        });

        this.enableForm();
        this.updateButtonStates();
        this.clearMessage();
    }

    protected handleEdit() {
        if (!this.selectedRow) return;
        this.isEditing = true;
        this.enableForm();
        this.updateButtonStates();
    }

    protected handleCancel() {
        this.isNew = false;
        this.isEditing = false;
        if (this.selectedRow) {
            this.populateFormFromRow(this.selectedRow);
        } else {
            this.maintenanceForm.querySelectorAll('input, select').forEach(i => (i as HTMLInputElement).value = '');
        }
        this.disableForm();
        this.updateButtonStates();
        this.clearMessage();
    }

    protected async handleSave() {
        if (!this.isNew && !this.selectedRow) return;

        const url = this.isNew ? this.getCreateUrl() : this.getUpdateUrl(this.selectedRow!.getAttribute('data-id')!);
        const formData = new URLSearchParams();

        this.metadata.maintenance_panel.fields.forEach(f => {
            const input = document.getElementById(`field-${f.name}`) as HTMLInputElement | HTMLSelectElement;
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
            const resp = await fetch(url, {
                method: 'POST',
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                body: formData
            });

            if (resp.ok) {
                window.location.reload();
            } else {
                const data = await resp.json();
                this.showMessage(data.detail || "Save failed", true);
            }
        } catch (err: any) {
            this.showMessage(err.message || "An error occurred during save", true);
        }
    }

    protected async handleDelete() {
        if (this.isDirty() && !confirm("Discard unsaved changes?")) return;
        
        if (!this.selectedRow || !confirm("Are you sure you want to delete this record?")) return;
        
        const url = this.getDeleteUrl(this.selectedRow.getAttribute('data-id')!);
        try {
            this.clearMessage();
            const resp = await fetch(url, { method: 'POST' });
            if (resp.ok) {
                window.location.reload();
            } else {
                const data = await resp.json();
                this.showMessage(data.detail || "Delete failed", true);
            }
        } catch (err: any) {
            this.showMessage(err.message || "An error occurred during delete", true);
        }
    }

    protected filterTable(field: string, query: string) {
        const rows = document.querySelectorAll('#browse-table tbody tr');
        const q = query.toLowerCase();
        
        // Find which column index matches 'field'
        const columns = this.metadata.browse_panel.columns;
        const colIndex = columns.findIndex(c => c.name === field);

        rows.forEach(row => {
            if (!q) {
                (row as HTMLElement).style.display = '';
                return;
            }
            if (colIndex === -1) return;

            const cell = (row as HTMLTableRowElement).cells[colIndex];
            if (cell) {
                const text = cell.textContent?.toLowerCase() || '';
                (row as HTMLElement).style.display = text.includes(q) ? '' : 'none';
            }
        });
    }

    protected getCreateUrl() { return ""; }
    protected getUpdateUrl(id: string) { return ""; }
    protected getDeleteUrl(id: string) { return ""; }
}
