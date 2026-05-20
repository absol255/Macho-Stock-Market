(function () {
    const signinCard = document.getElementById("signin-card");
    const tradeCard = document.getElementById("trade-card");
    const usernameInput = document.getElementById("username");
    const signinBtn = document.getElementById("signin-btn");
    const traderName = document.getElementById("trader-name");
    const balanceEl = document.getElementById("balance");
    const holdingsList = document.getElementById("holdings-list");
    const buyStock = document.getElementById("buy-stock");
    const buyQty = document.getElementById("buy-qty");
    const buyBtn = document.getElementById("buy-btn");
    const tradeMsg = document.getElementById("trade-msg");

    function showTrade() {
        signinCard.style.display = "none";
        tradeCard.style.display = "block";
    }

    function loadStocksSelect(stocks) {
        buyStock.innerHTML = stocks.map(function (s) {
            return (
                '<option value="' + s.id + '">' +
                s.stock_name + " — $" + s.value +
                "</option>"
            );
        }).join("");
    }

    function renderHoldings(data) {
        traderName.textContent = data.trader.username;
        balanceEl.textContent = "$" + data.trader.balance;

        if (!data.holdings.length) {
            holdingsList.innerHTML = "<p>No holdings yet.</p>";
            return;
        }

        holdingsList.innerHTML = data.holdings.map(function (h) {
            return (
                '<div class="user">' +
                "<div><strong>" + h.stock_name + "</strong><br>" +
                h.quantity + " shares @ $" + h.value +
                "</div>" +
                '<span class="balance">$' + h.worth + "</span>" +
                "</div>"
            );
        }).join("");
    }

    function refresh() {
        return fetch("/api/portfolio/me")
            .then(function (r) {
                if (r.status === 401) return null;
                return r.json();
            })
            .then(function (data) {
                if (!data) return;
                showTrade();
                renderHoldings(data);
            });
    }

    signinBtn.addEventListener("click", function () {
        const username = usernameInput.value.trim();
        if (!username) return;

        fetch("/api/portfolio/session", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ username: username }),
        })
            .then(function (r) { return r.json(); })
            .then(function () {
                return Promise.all([
                    fetch("/api/stocks").then(function (r) { return r.json(); }),
                    refresh(),
                ]);
            })
            .then(function (results) {
                if (results && results[0]) loadStocksSelect(results[0]);
            });
    });

    buyBtn.addEventListener("click", function () {
        tradeMsg.textContent = "";
        const stockId = parseInt(buyStock.value, 10);
        const quantity = parseInt(buyQty.value, 10);

        fetch("/api/portfolio/buy", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ stock_id: stockId, quantity: quantity }),
        })
            .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, d: d }; }); })
            .then(function (res) {
                if (!res.ok) {
                    tradeMsg.textContent = res.d.error || "Buy failed";
                    return;
                }
                tradeMsg.textContent = "Purchase complete!";
                refresh();
            });
    });

    Promise.all([
        fetch("/api/stocks").then(function (r) { return r.json(); }),
        refresh(),
    ]).then(function (results) {
        if (results[0]) loadStocksSelect(results[0]);
    });
})();
