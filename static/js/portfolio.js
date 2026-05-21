(function () {
    const signinCard = document.getElementById("signin-card");
    const tradeCard = document.getElementById("trade-card");
    const usernameInput = document.getElementById("username");
    const bankAccNum = document.getElementById("bankaccnum");
    const signinBtn = document.getElementById("signin-btn");
    const signinMsg = document.getElementById("signin-msg");
    const userName = document.getElementById("user-name");
    const bankDisplay = document.getElementById("bank-display");
    const balanceEl = document.getElementById("balance");
    const holdingsList = document.getElementById("holdings-list");
    const buyStock = document.getElementById("buy-stock");
    const sellStock = document.getElementById("sell-stock");
    const buyQty = document.getElementById("buy-qty");
    const sellQty = document.getElementById("sell-qty");
    const buyBtn = document.getElementById("buy-btn");
    const sellBtn = document.getElementById("sell-btn");
    const tradeMsg = document.getElementById("trade-msg");
    const logoutBtn = document.getElementById("logout-btn");

    function showTrade() {
        signinCard.style.display = "none";
        tradeCard.style.display = "block";
    }

    function showSignin() {
        tradeCard.style.display = "none";
        signinCard.style.display = "block";
    }

    function loadStocksSelect(stocks) {
        buyStock.innerHTML = stocks.map(function (s) {
            return (
                '<option value="' + s.id + '">' +
                s.stock_name + " — $" + s.value +
                "</option>"
            );
        }).join("");
        sellStock.innerHTML = stocks.map(function (s) {
            return (
                '<option value="' + s.id + '">' +
                s.stock_name + " — $" + s.value +
                "</option>"
            );
        }).join("");
    }

    function renderHoldings(data) {
        userName.textContent = data.user.username;
        bankDisplay.textContent = data.user.bank_account_number;
        balanceEl.textContent = data.user.macho_bucks;

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
        return fetch("/api/portfolio/me", { credentials: "include" })
            .then(function (r) {
                if (r.status === 401) return null;
                return r.json();
            })
            .then(function (data) {
                if (!data || data.error) return;
                showTrade();
                renderHoldings(data);
            });
    }

    signinBtn.addEventListener("click", function () {
        signinMsg.textContent = "";
        const username = usernameInput.value.trim();
        const bankAccountNumber = bankAccNum.value.trim();

        if (!username || !bankAccountNumber) {
            signinMsg.textContent = "Username and bank account number are required.";
            return;
        }

        fetch("/api/portfolio/session", {
            method: "POST",
            credentials: "include",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                username: username,
                bank_account_number: bankAccountNumber,
            }),
        })
            .then(function (r) {
                return r.json().then(function (d) {
                    return { ok: r.ok, d: d };
                });
            })
            .then(function (res) {
                if (!res.ok) {
                    signinMsg.textContent = res.d.error || "Sign in failed";
                    return;
                }
                return Promise.all([
                    fetch("/api/stocks").then(function (r) { return r.json(); }),
                    refresh(),
                ]);
            })
            .then(function (results) {
                if (results && results[0]) loadStocksSelect(results[0]);
            });
    });

    logoutBtn.addEventListener("click", function () {
        fetch("/api/portfolio/logout", {
            method: "POST",
            credentials: "include",
        }).then(function () {
            showSignin();
            signinMsg.textContent = "";
            usernameInput.value = "";
            bankAccNum.value = "";
        });
    });

    buyBtn.addEventListener("click", function () {
        tradeMsg.textContent = "";
        const stockId = parseInt(buyStock.value, 10);
        const quantity = parseInt(buyQty.value, 10);

        fetch("/api/portfolio/buy", {
            method: "POST",
            credentials: "include",
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

    sellBtn.addEventListener("click", function () {
        tradeMsg.textContent = "";
        const stockId = parseInt(sellStock.value, 10);
        const quantity = parseInt(sellQty.value, 10);

        fetch("/api/portfolio/sell", {
            method: "POST",
            credentials: "include",
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
