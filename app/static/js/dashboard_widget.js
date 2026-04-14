(function () {
    const mountNode = document.getElementById("react-dashboard-widget");
    const payloadNode = document.getElementById("dashboard-stats-data");

    if (!mountNode || !payloadNode) {
        return;
    }

    let data = {
        totalPre: 0,
        totalPost: 0,
        cardsIssued: 0,
        participants: 0,
    };

    try {
        data = Object.assign(data, JSON.parse(payloadNode.textContent || "{}"));
    } catch (error) {
        console.error("Failed to parse dashboard data", error);
    }

    function createElement(tagName, className, textValue) {
        const element = document.createElement(tagName);
        if (className) {
            element.className = className;
        }
        if (typeof textValue !== "undefined") {
            element.textContent = String(textValue);
        }
        return element;
    }

    function createStatItem(label, value, tone) {
        const item = createElement("article", "stat-item stat-" + tone);
        item.appendChild(createElement("p", "stat-label", label));
        item.appendChild(createElement("p", "stat-value", value));
        return item;
    }

    const completionRate = data.totalPre
        ? Math.round((data.totalPost / data.totalPre) * 100)
        : 0;

    const section = createElement("section", "editorial-widget");

    const intro = createElement("div", "widget-intro");
    intro.appendChild(createElement("p", "widget-kicker", "Live Snapshot"));
    intro.appendChild(createElement("h2", "", "Response Momentum"));
    intro.appendChild(
        createElement(
            "p",
            "widget-copy",
            "A concise pulse-check on survey completion and card delivery."
        )
    );
    section.appendChild(intro);

    const grid = createElement("div", "widget-grid");
    grid.appendChild(createStatItem("Pre Surveys", data.totalPre, "neutral"));
    grid.appendChild(createStatItem("Post Surveys", data.totalPost, "calm"));
    grid.appendChild(createStatItem("Cards Issued", data.cardsIssued, "warm"));
    grid.appendChild(createStatItem("Participants", data.participants, "neutral"));
    section.appendChild(grid);

    const band = createElement("div", "completion-band");
    band.appendChild(createElement("p", "", "Completion Rate"));
    band.appendChild(createElement("strong", "", completionRate + "%"));

    const meter = createElement("div", "completion-meter");
    meter.setAttribute("role", "progressbar");
    meter.setAttribute("aria-valuemin", "0");
    meter.setAttribute("aria-valuemax", "100");
    meter.setAttribute("aria-valuenow", String(completionRate));
    meter.setAttribute("aria-label", "Post survey completion rate");

    const fill = createElement("span");
    fill.style.width = Math.max(0, Math.min(completionRate, 100)) + "%";
    meter.appendChild(fill);
    band.appendChild(meter);
    section.appendChild(band);

    mountNode.replaceChildren(section);
})();
