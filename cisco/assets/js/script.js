$(document).ready(function() {
    // Inisialisasi DataTables untuk syslogs
    $('#syslogsTable').DataTable({
        "pageLength": 25,
        "order": [[0, "desc"]] // Urutkan berdasarkan ID secara descending
    });

    // Inisialisasi DataTables untuk mac_flap_logs
    $('#macFlapTable').DataTable({
        "pageLength": 25,
        "order": [[0, "desc"]] // Urutkan berdasarkan ID secara descending
    });
});