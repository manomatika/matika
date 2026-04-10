export {};

interface User {
    id: number;
    username: string;
    email: string;
}

interface RoleRow extends HTMLTableRowElement {
    dataset: DOMStringMap & {
        roleId: string;
        roleName: string;
        roleDesc: string;
        roleUsers: string;
    };
}

interface CellWithOriginal extends HTMLTableCellElement {
    dataset: DOMStringMap & {
        original: string;
    };
}

document.addEventListener('DOMContentLoaded', () => {
    const rolesTableBody = document.querySelector('#roles-table tbody');
    const assignedUsersTableBody = document.querySelector('#assigned-users-table tbody');
    const userSelector = document.getElementById('user-selector') as HTMLSelectElement;
    const btnAddUser = document.getElementById('btn-add-user') as HTMLButtonElement;
    const btnNew = document.getElementById('btn-new') as HTMLButtonElement;
    const btnEdit = document.getElementById('btn-edit') as HTMLButtonElement;
    const btnDelete = document.getElementById('btn-delete') as HTMLButtonElement;
    const btnSave = document.getElementById('btn-save') as HTMLButtonElement;
    const btnCancel = document.getElementById('btn-cancel') as HTMLButtonElement;
    const roleForm = document.getElementById('role-form') as HTMLFormElement;
    const formRoleName = document.getElementById('form-role-name') as HTMLInputElement;
    const formRoleDesc = document.getElementById('form-role-desc') as HTMLInputElement;
    const formUserIds = document.getElementById('form-user-ids') as HTMLInputElement;

    // Load allUsers from data attribute
    const allUsersData = document.getElementById('all-users-data')?.dataset.users;
    const allUsers: Record<number, User> = allUsersData ? JSON.parse(allUsersData) : {};

    let selectedRoleRow: RoleRow | null = null;
    let isEditing = false;
    let isNew = false;
    let currentAssignedUserIds: number[] = [];

    function selectRole(row: RoleRow) {
        if (isEditing || isNew) {
            if (selectedRoleRow === row) return;
            if (!confirm("Discard unsaved changes?")) return;
            cancelEdit();
        }

        if (selectedRoleRow) selectedRoleRow.classList.remove('selected-row');
        selectedRoleRow = row;
        selectedRoleRow.classList.add('selected-row');

        const userIdsStr = row.dataset.roleUsers;
        currentAssignedUserIds = userIdsStr ? userIdsStr.split(',').filter(s => s).map(Number) : [];
        
        updateUI();
    }

    function updateUI() {
        const isSystemRole = selectedRoleRow && (["Admin", "User"].includes(selectedRoleRow.dataset.roleName));
        
        btnEdit.disabled = !selectedRoleRow || isEditing || isNew;
        btnDelete.disabled = !selectedRoleRow || isEditing || isNew || isSystemRole!;
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
        if (!assignedUsersTableBody) return;
        assignedUsersTableBody.innerHTML = '';
        
        currentAssignedUserIds.forEach(id => {
            const u = allUsers[id];
            if (!u) return;
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
        if (selectedRoleRow) selectedRoleRow.classList.remove('selected-row');
        selectedRoleRow = null;
        currentAssignedUserIds = [];
        
        if (!rolesTableBody) return;
        const tr = document.createElement('tr') as RoleRow;
        tr.id = 'temp-row';
        tr.innerHTML = `
            <td>(new)</td>
            <td class="col-name"><input type="text" class="edit-input" placeholder="Role Name"></td>
            <td class="col-desc"><input type="text" class="edit-input" placeholder="Description"></td>
        `;
        rolesTableBody.prepend(tr);
        
        tr.querySelector('.col-name input')!.addEventListener('input', checkChanges);
        tr.querySelector('.col-desc input')!.addEventListener('input', checkChanges);

        updateUI();
    }

    function handleEdit() {
        if (!selectedRoleRow) return;
        isEditing = true;
        
        const nameCell = selectedRoleRow.querySelector('.col-name') as CellWithOriginal;
        const descCell = selectedRoleRow.querySelector('.col-desc') as CellWithOriginal;
        
        nameCell.innerHTML = `<input type="text" class="edit-input" value="${nameCell.dataset.original}">`;
        descCell.innerHTML = `<input type="text" class="edit-input" value="${descCell.dataset.original}">`;
        
        nameCell.querySelector('input')!.addEventListener('input', checkChanges);
        descCell.querySelector('input')!.addEventListener('input', checkChanges);

        updateUI();
    }

    function cancelEdit() {
        if (isNew) {
            const temp = document.getElementById('temp-row');
            if (temp) temp.remove();
            isNew = false;
            const firstRow = document.querySelector('#roles-table tbody tr') as RoleRow;
            if (firstRow) selectRole(firstRow);
        } else if (isEditing && selectedRoleRow) {
            const nameCell = selectedRoleRow.querySelector('.col-name') as CellWithOriginal;
            const descCell = selectedRoleRow.querySelector('.col-desc') as CellWithOriginal;
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
            const nameInput = selectedRoleRow.querySelector('.col-name input') as HTMLInputElement;
            const descInput = selectedRoleRow.querySelector('.col-desc input') as HTMLInputElement;
            const originalName = (selectedRoleRow.querySelector('.col-name') as CellWithOriginal).dataset.original;
            const originalDesc = (selectedRoleRow.querySelector('.col-desc') as CellWithOriginal).dataset.original;
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
        if (!userId) return;
        if (!currentAssignedUserIds.includes(userId)) {
            currentAssignedUserIds.push(userId);
            renderAssignedUsers();
            checkChanges();
        }
        userSelector.value = '';
    }

    function removeUserFromRole(userId: number) {
        currentAssignedUserIds = currentAssignedUserIds.filter(id => id !== userId);
        renderAssignedUsers();
        checkChanges();
    }

    function handleSave() {
        let name: string, desc: string;
        
        if (isNew) {
            const temp = document.getElementById('temp-row') as RoleRow;
            name = (temp.querySelector('.col-name input') as HTMLInputElement).value;
            desc = (temp.querySelector('.col-desc input') as HTMLInputElement).value;
            roleForm.action = '/admin/roles/create';
        } else {
            name = (selectedRoleRow!.querySelector('.col-name input') as HTMLInputElement).value;
            desc = (selectedRoleRow!.querySelector('.col-desc input') as HTMLInputElement).value;
            roleForm.action = `/admin/roles/update/${selectedRoleRow!.dataset.roleId}`;
        }
        
        formRoleName.value = name;
        formRoleDesc.value = desc;
        formUserIds.value = currentAssignedUserIds.join(',');
        
        roleForm.submit();
    }

    function handleDeleteRole() {
        if (!selectedRoleRow || isEditing || isNew) return;
        const roleId = selectedRoleRow.dataset.roleId;
        const roleName = selectedRoleRow.dataset.roleName;
        
        if (confirm(`Are you sure you want to delete role '${roleName}'?`)) {
            roleForm.action = `/admin/roles/delete/${roleId}`;
            roleForm.submit();
        }
    }

    // Event Listeners
    rolesTableBody?.addEventListener('click', (e) => {
        const target = e.target as HTMLElement;
        const row = target.closest('tr') as RoleRow;
        if (row && rolesTableBody.contains(row)) {
            selectRole(row);
        }
    });

    assignedUsersTableBody?.addEventListener('click', (e) => {
        const target = e.target as HTMLElement;
        if (target.classList.contains('remove-btn')) {
            const userId = parseInt(target.dataset.userId!);
            removeUserFromRole(userId);
        }
    });

    userSelector?.addEventListener('change', checkAddUserBtn);
    btnAddUser?.addEventListener('click', addUserToRole);
    btnNew?.addEventListener('click', handleNew);
    btnEdit?.addEventListener('click', handleEdit);
    btnDelete?.addEventListener('click', handleDeleteRole);
    btnSave?.addEventListener('click', handleSave);
    btnCancel?.addEventListener('click', cancelEdit);

    // Initial Selection
    const firstRow = document.querySelector('#roles-table tbody tr') as RoleRow;
    if (firstRow) selectRole(firstRow);
});
