import { injectCsrfToken } from "./csrf.js";
document.addEventListener('DOMContentLoaded', () => {
    let selectedRow = null;
    let isEditing = false;
    let isNew = false;
    const userTableBody = document.querySelector('#user-table tbody');
    const btnNew = document.getElementById('btn-new');
    const btnEdit = document.getElementById('btn-edit');
    const btnSave = document.getElementById('btn-save');
    const btnCancel = document.getElementById('btn-cancel');
    const btnDelete = document.getElementById('btn-delete');
    const actionForm = document.getElementById('action-form');
    const formUsername = document.getElementById('form-username');
    const formEmail = document.getElementById('form-email');
    const formForcePw = document.getElementById('form-force-pw');
    function selectRow(row) {
        if (selectedRow === row)
            return;
        if (isEditing || isNew) {
            if (!confirm("Discard unsaved changes?"))
                return;
            cancelEdit(selectedRow);
            isEditing = false;
            isNew = false;
        }
        if (selectedRow)
            selectedRow.classList.remove('selected-row');
        selectedRow = row;
        selectedRow.classList.add('selected-row');
        updateButtonStates();
    }
    function updateButtonStates() {
        const isSystemSelf = (selectedRow === null || selectedRow === void 0 ? void 0 : selectedRow.dataset.isSelf) === 'true';
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
            const usernameInput = selectedRow.querySelector('.col-username input');
            const emailInput = selectedRow.querySelector('.col-email input');
            btnSave.disabled = !usernameInput.value || !emailInput.value;
            btnCancel.disabled = false;
            return;
        }
        if (!isEditing) {
            btnSave.disabled = true;
            btnCancel.disabled = true;
            return;
        }
        const emailInput = selectedRow.querySelector('.col-email input');
        const forcePwInput = selectedRow.querySelector('.col-force-pw input');
        const currentEmail = emailInput.value;
        const currentForcePw = forcePwInput.checked;
        const emailCell = selectedRow.querySelector('.col-email');
        const forcePwCell = selectedRow.querySelector('.col-force-pw');
        const originalEmail = emailCell.dataset.original;
        const originalForcePw = forcePwCell.dataset.original === 'true';
        const changed = (currentEmail !== originalEmail) || (currentForcePw !== originalForcePw);
        btnSave.disabled = !changed;
        btnCancel.disabled = false;
    }
    function handleNew() {
        isNew = true;
        if (selectedRow)
            selectedRow.classList.remove('selected-row');
        const tr = document.createElement('tr');
        tr.id = 'temp-row';
        tr.innerHTML = `
            <td>(new)</td>
            <td class="col-username"><input type="text" class="edit-input" placeholder="Username"></td>
            <td class="col-email"><input type="email" class="edit-input" placeholder="Email"></td>
            <td>local</td>
            <td class="col-force-pw"><input type="checkbox" checked disabled> (Required)</td>
        `;
        userTableBody === null || userTableBody === void 0 ? void 0 : userTableBody.prepend(tr);
        selectedRow = tr;
        selectedRow.classList.add('selected-row');
        tr.querySelector('.col-username input').addEventListener('input', checkChanges);
        tr.querySelector('.col-email input').addEventListener('input', checkChanges);
        updateButtonStates();
    }
    function handleEdit() {
        if (!selectedRow)
            return;
        isEditing = true;
        const emailCell = selectedRow.querySelector('.col-email');
        const forcePwCell = selectedRow.querySelector('.col-force-pw');
        const originalEmail = emailCell.dataset.original;
        const originalForcePw = forcePwCell.dataset.original === 'true';
        // Use DOM construction to avoid XSS — never interpolate user data into innerHTML.
        const emailInput = document.createElement("input");
        emailInput.type = "text";
        emailInput.className = "edit-input";
        emailInput.value = originalEmail !== null && originalEmail !== void 0 ? originalEmail : "";
        emailCell.textContent = "";
        emailCell.appendChild(emailInput);
        const pwCheckbox = document.createElement("input");
        pwCheckbox.type = "checkbox";
        if (originalForcePw)
            pwCheckbox.checked = true;
        forcePwCell.textContent = "";
        forcePwCell.appendChild(pwCheckbox);
        emailInput.addEventListener("input", checkChanges);
        pwCheckbox.addEventListener("change", checkChanges);
        updateButtonStates();
    }
    function cancelEdit(row) {
        if (isNew) {
            row.remove();
            isNew = false;
            const firstRow = document.querySelector('#user-table tbody tr:not(#temp-row)');
            if (firstRow) {
                selectedRow = null;
                selectRow(firstRow);
            }
            return;
        }
        const emailCell = row.querySelector('.col-email');
        const forcePwCell = row.querySelector('.col-force-pw');
        const originalEmail = emailCell.dataset.original;
        const originalForcePw = forcePwCell.dataset.original === 'true';
        emailCell.textContent = originalEmail;
        // In a real app we'd need to restore the localized Yes/No from a data attribute or similar
        // For now, let's just use the original logic which was text-based.
        forcePwCell.textContent = originalForcePw ? 'Yes' : 'No';
    }
    function handleCancel() {
        if (!selectedRow || (!isEditing && !isNew))
            return;
        cancelEdit(selectedRow);
        isEditing = false;
        isNew = false;
        updateButtonStates();
    }
    function handleSave() {
        if (!selectedRow || (!isEditing && !isNew))
            return;
        if (isNew) {
            const usernameInput = selectedRow.querySelector('.col-username input');
            const emailInput = selectedRow.querySelector('.col-email input');
            actionForm.action = '/admin/users/create';
            formUsername.value = usernameInput.value;
            formEmail.value = emailInput.value;
            injectCsrfToken(actionForm);
            actionForm.submit();
            return;
        }
        const userId = selectedRow.dataset.userId;
        const emailInput = selectedRow.querySelector('.col-email input');
        const forcePwInput = selectedRow.querySelector('.col-force-pw input');
        const email = emailInput.value;
        const forcePw = forcePwInput.checked;
        actionForm.action = `/admin/users/update/${userId}`;
        formEmail.value = email;
        if (!forcePw) {
            formForcePw.name = "";
        }
        else {
            formForcePw.name = "force_password_change";
            formForcePw.value = "true";
        }
        injectCsrfToken(actionForm);
        actionForm.submit();
    }
    function handleDeleteUser() {
        if (!selectedRow || isEditing || isNew)
            return;
        const userId = selectedRow.dataset.userId;
        const isSelf = selectedRow.dataset.isSelf === 'true';
        if (isSelf)
            return;
        if (confirm('Are you sure you want to delete this user?')) {
            actionForm.action = `/admin/users/delete/${userId}`;
            injectCsrfToken(actionForm);
            actionForm.submit();
        }
    }
    // Attach Event Listeners
    if (userTableBody) {
        userTableBody.addEventListener('click', (e) => {
            const target = e.target;
            const row = target.closest('tr');
            if (row && userTableBody.contains(row)) {
                if (row.id === 'temp-row')
                    return;
                selectRow(row);
            }
        });
    }
    btnNew === null || btnNew === void 0 ? void 0 : btnNew.addEventListener('click', handleNew);
    btnEdit === null || btnEdit === void 0 ? void 0 : btnEdit.addEventListener('click', handleEdit);
    btnSave === null || btnSave === void 0 ? void 0 : btnSave.addEventListener('click', handleSave);
    btnCancel === null || btnCancel === void 0 ? void 0 : btnCancel.addEventListener('click', handleCancel);
    btnDelete === null || btnDelete === void 0 ? void 0 : btnDelete.addEventListener('click', handleDeleteUser);
    // Initial Selection
    const firstRow = document.querySelector('#user-table tbody tr');
    if (firstRow)
        selectRow(firstRow);
});
