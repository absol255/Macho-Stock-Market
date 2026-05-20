(function () {
    const listEl = document.getElementById("stock-list");
    if (!listEl) return;

    function drawSparkline(points, width, height) {
        if (!points || points.length < 2) {
            return '<svg width="' + width + '" height="' + height + '"></svg>';
        }

        const values = points.map(function (p) { return p.value; });
        const min = Math.min.apply(null, values);
        const max = Math.max.apply(null, values);
        const range = max - min || 1;
        const pad = 4;
        const innerW = width - pad * 2;
        const innerH = height - pad * 2;
        const step = innerW / (values.length - 1);

        const coords = values.map(function (v, i) {
            const x = pad + i * step;
            const y = pad + innerH - ((v - min) / range) * innerH;
            return x.toFixed(1) + "," + y.toFixed(1);
        });

        const first = values[0];
        const last = values[values.length - 1];
        const up = last >= first;
        const stroke = up ? "#4ade80" : "#f87171";

        return (
            '<svg width="' + width + '" height="' + height + '" viewBox="0 0 ' + width + ' ' + height + '">' +
            '<polyline fill="none" stroke="' + stroke + '" stroke-width="2" stroke-linejoin="round" points="' + coords.join(" ") + '"/>' +
            "</svg>"
        );
    }

    function changeLabel(points, current) {
        if (!points || points.length < 2) {
            return '<span class="balance">$' + current + "</span>";
        }
        const first = points[0].value;
        const pct = first ? Math.round(((current - first) / first) * 1000) / 10 : 0;
        const sign = pct >= 0 ? "+" : "";
        const color = pct >= 0 ? "#4ade80" : "#f87171";
        return (
            '<span style="color:' + color + ';font-weight:bold">' + sign + pct + "%</span> " +
            '<span class="balance">$' + current + "</span>"
        );
    }

    function render(stocks, history) {
        if (!stocks.length) {
            listEl.innerHTML = "<p>No stocks yet. Admins can add them in the Admin Panel.</p>";
            return;
        }

        listEl.innerHTML = stocks.map(function (stock) {
            const pts = history[String(stock.id)] || [{ value: stock.value, t: "" }];
            return (
                '<div class="user">' +
                '<div>' +
                "<strong>" + stock.stock_name + "</strong><br>" +
                changeLabel(pts, stock.value) +
                "</div>" +
                drawSparkline(pts, 140, 48) +
                "</div>"
            );
        }).join("");
    }

    Promise.all([
        fetch("/api/stocks").then(function (r) { return r.json(); }),
        fetch("/api/stocks/history").then(function (r) { return r.json(); }),
    ])
        .then(function (results) {
            render(results[0], results[1]);
        })
        .catch(function () {
            listEl.innerHTML = "<p>Could not load stocks.</p>";
        });
})();
