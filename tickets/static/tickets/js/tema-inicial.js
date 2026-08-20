(function () {
    var tema = localStorage.getItem('theme');
    if (tema === 'dark' || (!tema && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
        document.documentElement.setAttribute('data-bs-theme', 'dark');
    }
    if (localStorage.getItem('sidebarCollapsed') === 'true') {
        document.documentElement.setAttribute('data-sidebar-collapsed', 'true');
    }
})();
