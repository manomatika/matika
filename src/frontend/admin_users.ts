export {};

interface UserRow extends HTMLTableRowElement {
    dataset: DOMStringMap & {
        userId: string;
        isSelf: string;
    };
}

interface CellWithOriginal extends HTMLTableCellElement {
    dataset: DOMStringMap & {
        original: string;
    };
}

document.addEventListener('DOMContentLoaded', () => {
    let selectedRow: UserRow | null = null;
    let isEditing = false;
    let isNew = false;

    const userTableBody = document.querySelector('#user-table tbody');
    const btnNew = document.getElementById('btn-new') as HTMLButtonElement;
    const btnEdit = document.getElementById('btn-edit') as HTMLButtonElement;
    const btnSave = document.getElementById('btn-save') as HTMLButtonElement;
    const btnCancel = document.getElementById('btn-cancel') as HTMLButtonElement;
    const btnDelete = document.getElementById('btn-delete') as HTMLButtonElement;
    const actionForm = document.getElementById('action-form') as HTMLFormElement;
    const formUsername = document.getElementById('form-username') as HTMLInputElement;
    const formEmail = document.getElementById('form-email') as HTMLInputElement;
    const formForcePw = document.getElementById('form-force-pw') as HTMLInputElement;

    function selectRow(row: UserRow) {
        if (selectedRow === row) return;

        if (isEditing || isNew) {
            if (!confirm("Discard unsaved changes?")) return;
            cancelEdit(selectedRow!);
            isEditing = false;
            isNew = false;
        }

        if (selectedRow) selectedRow.classList.remove('selected-row');
        
        selectedRow = row;
        selectedRow.classList.add('selected-row');
        
        updateButtonStates();
    }

    function updateButtonStates() {
        const isSystemSelf = selectedRow?.dataset.isSelf === 'true';
        btnDelete.disabled = isEditing || isNew || isSystemSelf || !selectedRow;
        btnEdit.disabled = isEditing || isNew || !selectedRow;
        btnNew.disabled = isEditing || isNew;
        
        checkChanges();
    }

    function checkChanges() {
        if (!selectedRow) {
            btnSave.disabled = true;
            btnCancel.disabled = true;
            return;
        }

        if (isNew) {
            const usernameInput = selectedRow.querySelector('.col-username input') as HTMLInputElement;
            const emailInput = selectedRow.querySelector('.col-email input') as HTMLInputElement;
            btnSave.disabled = !usernameInput.value || !emailInput.value;
            btnCancel.disabled = false;
            return;
        }

        if (!isEditing) {
            btnSave.disabled = true;
            btnCancel.disabled = true;
            return;
        }

        const emailInput = selectedRow.querySelector('.col-email input') as HTMLInputElement;
        const forcePwInput = selectedRow.querySelector('.col-force-pw input') as HTMLInputElement;
        
        const currentEmail = emailInput.value;
        const currentForcePw = forcePwInput.checked;
        
        const emailCell = selectedRow.querySelector('.col-email') as CellWithOriginal;
        const forcePwCell = selectedRow.querySelector('.col-force-pw') as CellWithOriginal;
        
        const originalEmail = emailCell.dataset.original;
        const originalForcePw = forcePwCell.dataset.original === 'true';
        
        const changed = (currentEmail !== originalEmail) || (currentForcePw !== originalForcePw);
        
        btnSave.disabled = !changed;
        btnCancel.disabled = false;
    }

    function handleNew() {
        isNew = true;
        if (selectedRow) selectedRow.classList.remove('selected-row');
        
        const tr = document.createElement('tr') as UserRow;
        tr.id = 'temp-row';
        tr.innerHTML = `
            <td>(new)</td>
            <td class="col-username"><input type="text" class="edit-input" placeholder="Username"></td>
            <td class="col-email"><input type="email" class="edit-input" placeholder="Email"></td>
            <td>local</td>
            <td class="col-force-pw"><input type="checkbox" checked disabled> (Required)</td>
        `;
        userTableBody?.prepend(tr);
        selectedRow = tr;
        selectedRow.classList.add('selected-row');

        tr.querySelector('.col-username input')!.addEventListener('input', checkChanges);
        tr.querySelector('.col-email input')!.addEventListener('input', checkChanges);

        updateButtonStates();
    }

    function handleEdit() {
        if (!selectedRow) return;
        isEditing = true;
        
        const emailCell = selectedRow.querySelector('.col-email') as CellWithOriginal;
        const forcePwCell = selectedRow.querySelector('.col-force-pw') as CellWithOriginal;
        
        const originalEmail = emailCell.dataset.original;
        const originalForcePw = forcePwCell.dataset.original === 'true';
        
        emailCell.innerHTML = `<input type="text" class="edit-input" value="${originalEmail}">`;
        forcePwCell.innerHTML = `<input type="checkbox" ${originalForcePw ? 'checked' : ''}>`;
        
        emailCell.querySelector('input')!.addEventListener('input', checkChanges);
        forcePwCell.querySelector('input')!.addEventListener('change', checkChanges);

        updateButtonStates();
    }

    function cancelEdit(row: UserRow) {
        if (isNew) {
            row.remove();
            isNew = false;
            const firstRow = document.querySelector('#user-table tbody tr:not(#temp-row)') as UserRow;
            if (firstRow) {
                selectedRow = null;
                selectRow(firstRow);
            }
            return;
        }

        const emailCell = row.querySelector('.col-email') as CellWithOriginal;
        const forcePwCell = row.querySelector('.col-force-pw') as CellWithOriginal;
        
        const originalEmail = emailCell.dataset.original;
        const originalForcePw = forcePwCell.dataset.original === 'true';
        
        emailCell.textContent = originalEmail;
        // In a real app we'd need to restore the localized Yes/No from a data attribute or similar
        // For now, let's just use the original logic which was text-based.
        forcePwCell.textContent = originalForcePw ? 'Yes' : 'No';
    }

    function handleCancel() {
        if (!selectedRow || (!isEditing && !isNew)) return;
        cancelEdit(selectedRow);
        isEditing = false;
        isNew = false;
        updateButtonStates();
    }

    function handleSave() {
        if (!selectedRow || (!isEditing && !isNew)) return;
        
        if (isNew) {
            const usernameInput = selectedRow.querySelector('.col-username input') as HTMLInputElement;
            const emailInput = selectedRow.querySelector('.col-email input') as HTMLInputElement;
            
            actionForm.action = '/admin/users/create';
            formUsername.value = usernameInput.value;
            formEmail.value = emailInput.value;
            actionForm.submit();
            return;
        }

        const userId = selectedRow.dataset.userId;
        const emailInput = selectedRow.querySelector('.col-email input') as HTMLInputElement;
        const forcePwInput = selectedRow.querySelector('.col-force-pw input') as HTMLInputElement;
        
        const email = emailInput.value;
        const forcePw = forcePwInput.checked;
        
        actionForm.action = `/admin/users/update/${userId}`;
        formEmail.value = email;
        
        if (!forcePw) {
            formForcePw.name = ""; 
        } else {
            formForcePw.name = "force_password_change";
            formForcePw.value = "true";
        }

        actionForm.submit();
    }

    function handleDeleteUser() {
        if (!selectedRow || isEditing || isNew) return;
        const userId = selectedRow.dataset.userId;
        const isSelf = selectedRow.dataset.isSelf === 'true';
        
        if (isSelf) return;
        
        if (confirm('Are you sure you want to delete this user?')) {
            actionForm.action = `/admin/users/delete/${userId}`;
            actionForm.submit();
        }
    }

    // Attach Event Listeners
    if (userTableBody) {
        userTableBody.addEventListener('click', (e) => {
            const target = e.target as HTMLElement;
            const row = target.closest('tr') as UserRow;
            if (row && userTableBody.contains(row)) {
                if (row.id === 'temp-row') return;
                selectRow(row);
            }
        });
    }

    btnNew?.addEventListener('click', handleNew);
    btnEdit?.addEventListener('click', handleEdit);
    btnSave?.addEventListener('click', handleSave);
    btnCancel?.addEventListener('click', handleCancel);
    btnDelete?.addEventListener('click', handleDeleteUser);

    // Initial Selection
    const firstRow = document.querySelector('#user-table tbody tr') as UserRow;
    if (firstRow) selectRow(firstRow);
});
