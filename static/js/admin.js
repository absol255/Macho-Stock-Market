(function () {
    const listEl = document.getElementById("admin-stock-list");
    const newName = document.getElementById("new-name");
    const newValue = document.getElementById("new-value");
    const addBtn = document.getElementById("add-btn");
    const adminMsg = document.getElementById("admin-msg");
    const addStockList = document.getElementById("add-stock-list");
    const addStockBtn = document.getElementById("add-stock-btn");
    const stockUsername = document.getElementById("stock-username");
    const stockValue = document.getElementById("stock-value");

    function message(text) {
        adminMsg.textContent = text;
    }

    function load() {
        fetch("/api/admin/stocks", { credentials: "include" })
            .then(function (r) {
                if (r.status === 401) {
                    window.location.href = "/login";
                    return null;
                }
                return r.json();
            })
            .then(function (stocks) {
                if (!stocks) return;
                if (!stocks.length) {
                    listEl.innerHTML = "<p>No stocks yet.</p>";
                    return;
                }

                listEl.innerHTML = stocks.map(function (stock) {
                    return (
                        '<div class="user">' +
                        '<div style="flex:1">' +
                        '<input type="text" value="' + stock.stock_name + '" data-id="' + stock.id + '" data-field="name">' +
                        '<input type="number" value="' + stock.value + '" data-id="' + stock.id + '" data-field="value">' +
                        "</div>" +
                        '<button class="button" data-save="' + stock.id + '" type="button">Save</button>' +
                        '<button class="button" data-del="' + stock.id + '" type="button">Delete</button>' +
                        "</div>"
                    );
                }).join("");

                listEl.querySelectorAll("[data-save]").forEach(function (btn) {
                    btn.addEventListener("click", function () {
                        const id = btn.getAttribute("data-save");
                        const row = btn.closest(".user");
                        const nameInput = row.querySelector('[data-field="name"]');
                        const valueInput = row.querySelector('[data-field="value"]');

                        fetch("/api/admin/stocks/" + id, {
                            method: "PATCH",
                            credentials: "include",
                            headers: { "Content-Type": "application/json" },
                            body: JSON.stringify({
                                stock_name: nameInput.value.trim(),
                                value: parseFloat(valueInput.value, 10),
                            }),
                        })
                            .then(function (r) { return r.json(); })
                            .then(function () {
                                message("Saved.");
                                load();
                            });
                    });
                });

                listEl.querySelectorAll("[data-del]").forEach(function (btn) {
                    btn.addEventListener("click", function () {
                        const id = btn.getAttribute("data-del");
                        if (!confirm("Delete this stock?")) return;

                        fetch("/api/admin/stocks/" + id, { method: "DELETE", credentials: "include" })
                            .then(function () {
                                message("Deleted.");
                                load();
                            });
                    });
                });

                addStockList.innerHTML = stocks.map(function (s) {
                    return (
                        '<option value="' + s.id + '">' +
                        s.stock_name + " — $" + s.value +
                        "</option>"
                    );
                }).join("");
            });
    }

    addBtn.addEventListener("click", function () {
        const name = newName.value.trim();
        const value = parseFloat(newValue.value, 10);
        if (!name) return;

        fetch("/api/admin/stocks", {
            method: "POST",
            credentials: "include",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ stock_name: name, value: value || 0 }),
        })
            .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, d: d }; }); })
            .then(function (res) {
                if (!res.ok) {
                    message(res.d.error || "Could not add stock");
                    return;
                }
                newName.value = "";
                newValue.value = "";
                message("Stock added.");
                load();
            });
    });

    addStockBtn.addEventListener("click", function () {
        const username = String(stockUsername.value)
        const stockId = parseFloat(addStockList.value, 10);
        const quantity = parseFloat(stockValue.value, 10);
        if (!stockId) return;
        if (!username) return;

        fetch("/api/admin/addstock", {
            method: "POST",
            credentials: "include",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({username: username, stock_id: stockId, quantity: quantity || 0 }),
        })
            .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, d: d }; }); })
            .then(function (res) {
                if (!res.ok) {
                    message(res.d.error || "Could not add stock to machoer");
                    return;
                }
                newName.value = "";
                newValue.value = "";
                message("Stock added to machoer.");
                load();
            });
    });

    load();
})();
