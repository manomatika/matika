import { injectCsrfToken } from "./csrf.js";
document.addEventListener('DOMContentLoaded', () => {
    var _a;
    const rolesTableBody = document.querySelector('#roles-table tbody');
    const assignedUsersTableBody = document.querySelector('#assigned-users-table tbody');
    const userSelector = document.getElementById('user-selector');
    const btnAddUser = document.getElementById('btn-add-user');
    const btnNew = document.getElementById('btn-new');
    const btnEdit = document.getElementById('btn-edit');
    const btnDelete = document.getElementById('btn-delete');
    const btnSave = document.getElementById('btn-save');
    const btnCancel = document.getElementById('btn-cancel');
    const roleForm = document.getElementById('role-form');
    const formRoleName = document.getElementById('form-role-name');
    const formRoleDesc = document.getElementById('form-role-desc');
    const formUserIds = document.getElementById('form-user-ids');
    // Load allUsers from data attribute
    const allUsersData = (_a = document.getElementById('all-users-data')) === null || _a === void 0 ? void 0 : _a.dataset.users;
    const allUsers = allUsersData ? JSON.parse(allUsersData) : {};
    let selectedRoleRow = null;
    let isEditing = false;
    let isNew = false;
    let currentAssignedUserIds = [];
    function selectRole(row) {
        if (isEditing || isNew) {
            if (selectedRoleRow === row)
                return;
            if (!confirm("Discard unsaved changes?"))
                return;
            cancelEdit();
        }
        if (selectedRoleRow)
            selectedRoleRow.classList.remove('selected-row');
        selectedRoleRow = row;
        selectedRoleRow.classList.add('selected-row');
        const userIdsStr = row.dataset.roleUsers;
        currentAssignedUserIds = userIdsStr ? userIdsStr.split(',').filter(s => s).map(Number) : [];
        updateUI();
    }
    function updateUI() {
        const isSystemRole = selectedRoleRow && (["Admin", "User"].includes(selectedRoleRow.dataset.roleName));
        btnEdit.disabled = !selectedRoleRow || isEditing || isNew;
        btnDelete.disabled = !selectedRoleRow || isEditing || isNew || isSystemRole;
        btnNew.disabled = isEditing || isNew;
        renderAssignedUsers();
        userSelector.disabled = !(isEditing || isNew);
        checkAddUserBtn();
        checkChanges();
    }
    function checkAddUserBtn() {
        btnAddUser.disabled = !(isEditing || isNew) || !userSelector.value;
    }
    function renderAssignedUsers() {
        if (!assignedUsersTableBody)
            return;
        assignedUsersTableBody.innerHTML = '';
        currentAssignedUserIds.forEach(id => {
            const u = allUsers[id];
            if (!u)
                return;
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>${u.id}</td>
                <td>${u.username}</td>
                <td>${u.email}</td>
                <td>
                    <button class="remove-btn" data-user-id="${id}" ${!(isEditing || isNew) ? 'disabled style="opacity:0.3"' : ''}>Remove</button>
                </td>
            `;
            assignedUsersTableBody.appendChild(tr);
        });
    }
    function handleNew() {
        isNew = true;
        isEditing = false;
        if (selectedRoleRow)
            selectedRoleRow.classList.remove('selected-row');
        selectedRoleRow = null;
        currentAssignedUserIds = [];
        if (!rolesTableBody)
            return;
        const tr = document.createElement('tr');
        tr.id = 'temp-row';
        tr.innerHTML = `
            <td>(new)</td>
            <td class="col-name"><input type="text" class="edit-input" placeholder="Role Name"></td>
            <td class="col-desc"><input type="text" class="edit-input" placeholder="Description"></td>
        `;
        rolesTableBody.prepend(tr);
        selectedRoleRow = tr;
        tr.querySelector('.col-name input').addEventListener('input', checkChanges);
        tr.querySelector('.col-desc input').addEventListener('input', checkChanges);
        updateUI();
    }
    function handleEdit() {
        var _a, _b;
        if (!selectedRoleRow)
            return;
        isEditing = true;
        const nameCell = selectedRoleRow.querySelector('.col-name');
        const descCell = selectedRoleRow.querySelector('.col-desc');
        // DOM construction to prevent XSS — never interpolate stored values into innerHTML.
        const nameInput = document.createElement("input");
        nameInput.type = "text";
        nameInput.className = "edit-input";
        nameInput.value = (_a = nameCell.dataset.original) !== null && _a !== void 0 ? _a : "";
        nameCell.textContent = "";
        nameCell.appendChild(nameInput);
        const descInput = document.createElement("input");
        descInput.type = "text";
        descInput.className = "edit-input";
        descInput.value = (_b = descCell.dataset.original) !== null && _b !== void 0 ? _b : "";
        descCell.textContent = "";
        descCell.appendChild(descInput);
        nameCell.querySelector('input').addEventListener('input', checkChanges);
        descCell.querySelector('input').addEventListener('input', checkChanges);
        updateUI();
    }
    function cancelEdit() {
        if (isNew) {
            const temp = document.getElementById('temp-row');
            if (temp)
                temp.remove();
            isNew = false;
            const firstRow = document.querySelector('#roles-table tbody tr');
            if (firstRow)
                selectRole(firstRow);
        }
        else if (isEditing && selectedRoleRow) {
            const nameCell = selectedRoleRow.querySelector('.col-name');
            const descCell = selectedRoleRow.querySelector('.col-desc');
            nameCell.textContent = nameCell.dataset.original;
            descCell.textContent = descCell.dataset.original;
            const userIdsStr = selectedRoleRow.dataset.roleUsers;
            currentAssignedUserIds = userIdsStr ? userIdsStr.split(',').filter(s => s).map(Number) : [];
            isEditing = false;
        }
        updateUI();
    }
    function checkChanges() {
        if (!(isEditing || isNew)) {
            btnSave.disabled = true;
            btnCancel.disabled = true;
            return;
        }
        let changed = isNew;
        if (isEditing && selectedRoleRow) {
            const nameInput = selectedRoleRow.querySelector('.col-name input');
            const descInput = selectedRoleRow.querySelector('.col-desc input');
            const originalName = selectedRoleRow.querySelector('.col-name').dataset.original;
            const originalDesc = selectedRoleRow.querySelector('.col-desc').dataset.original;
            const originalUserIdsStr = selectedRoleRow.dataset.roleUsers;
            const originalUserIds = originalUserIdsStr ? originalUserIdsStr.split(',').sort().join(',') : '';
            const currentUserIds = currentAssignedUserIds.slice().sort().join(',');
            changed = (nameInput.value !== originalName) ||
                (descInput.value !== originalDesc) ||
                (currentUserIds !== originalUserIds);
        }
        btnSave.disabled = !changed;
        btnCancel.disabled = false;
    }
    function addUserToRole() {
        const userId = parseInt(userSelector.value);
        if (!userId)
            return;
        if (!currentAssignedUserIds.includes(userId)) {
            currentAssignedUserIds.push(userId);
            renderAssignedUsers();
            checkChanges();
        }
        userSelector.value = '';
    }
    function removeUserFromRole(userId) {
        currentAssignedUserIds = currentAssignedUserIds.filter(id => id !== userId);
        renderAssignedUsers();
        checkChanges();
    }
    function handleSave() {
        let name, desc;
        if (isNew) {
            const temp = document.getElementById('temp-row');
            name = temp.querySelector('.col-name input').value;
            desc = temp.querySelector('.col-desc input').value;
            roleForm.action = '/admin/roles/create';
        }
        else {
            name = selectedRoleRow.querySelector('.col-name input').value;
            desc = selectedRoleRow.querySelector('.col-desc input').value;
            roleForm.action = `/admin/roles/update/${selectedRoleRow.dataset.roleId}`;
        }
        formRoleName.value = name;
        formRoleDesc.value = desc;
        formUserIds.value = currentAssignedUserIds.join(',');
        injectCsrfToken(roleForm);
        roleForm.submit();
    }
    function handleDeleteRole() {
        if (!selectedRoleRow || isEditing || isNew)
            return;
        const roleId = selectedRoleRow.dataset.roleId;
        const roleName = selectedRoleRow.dataset.roleName;
        if (confirm(`Are you sure you want to delete role '${roleName}'?`)) {
            roleForm.action = `/admin/roles/delete/${roleId}`;
            injectCsrfToken(roleForm);
            roleForm.submit();
        }
    }
    // Event Listeners
    rolesTableBody === null || rolesTableBody === void 0 ? void 0 : rolesTableBody.addEventListener('click', (e) => {
        const target = e.target;
        const row = target.closest('tr');
        if (row && rolesTableBody.contains(row)) {
            if (row.id === 'temp-row')
                return;
            selectRole(row);
        }
    });
    assignedUsersTableBody === null || assignedUsersTableBody === void 0 ? void 0 : assignedUsersTableBody.addEventListener('click', (e) => {
        const target = e.target;
        if (target.classList.contains('remove-btn')) {
            const userId = parseInt(target.dataset.userId);
            removeUserFromRole(userId);
        }
    });
    userSelector === null || userSelector === void 0 ? void 0 : userSelector.addEventListener('change', checkAddUserBtn);
    btnAddUser === null || btnAddUser === void 0 ? void 0 : btnAddUser.addEventListener('click', addUserToRole);
    btnNew === null || btnNew === void 0 ? void 0 : btnNew.addEventListener('click', handleNew);
    btnEdit === null || btnEdit === void 0 ? void 0 : btnEdit.addEventListener('click', handleEdit);
    btnDelete === null || btnDelete === void 0 ? void 0 : btnDelete.addEventListener('click', handleDeleteRole);
    btnSave === null || btnSave === void 0 ? void 0 : btnSave.addEventListener('click', handleSave);
    btnCancel === null || btnCancel === void 0 ? void 0 : btnCancel.addEventListener('click', cancelEdit);
    // Initial Selection
    const firstRow = document.querySelector('#roles-table tbody tr');
    if (firstRow)
        selectRole(firstRow);
});
