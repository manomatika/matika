export {};

document.addEventListener('DOMContentLoaded', () => {
    // Handle menu navigation
    const menuItems = document.querySelectorAll('.menu-item[data-href], .dropdown div:not(.menu-separator)');
    
    menuItems.forEach(item => {
        item.addEventListener('click', () => {
            const href = item.getAttribute('data-href');
            const target = item.getAttribute('data-target');
            const action = item.getAttribute('data-action');

            if (action === 'reload') {
                location.reload();
            } else if (href) {
                if (target === '_blank') {
                    window.open(href, '_blank');
                } else {
                    window.location.href = href;
                }
            }
        });
    });
});
