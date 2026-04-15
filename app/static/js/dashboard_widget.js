(function () {
    const mountNode = document.getElementById("react-dashboard-widget");
    const payloadNode = document.getElementById("dashboard-stats-data");
    const participantListNode = document.getElementById("participant-list");

    if (!mountNode || !payloadNode) {
        return;
    }

    let state = {
        totalPre: 0,
        totalPost: 0,
        cardsIssued: 0,
        participants: 0,
        recentParticipants: [],
        summaryUrl: "",
        participantDetailTemplate: "/dashboard/participant/__CODE__",
    };

    try {
        state = Object.assign(state, JSON.parse(payloadNode.textContent || "{}"));
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

    function formatDate(value) {
        if (!value) {
            return "Unknown date";
        }

        const parsed = new Date(value);
        if (Number.isNaN(parsed.getTime())) {
            return "Unknown date";
        }
        return parsed.toISOString().slice(0, 10);
    }

    function buildParticipantUrl(code) {
        const encoded = encodeURIComponent(code);
        return String(state.participantDetailTemplate || "").replace("__CODE__", encoded);
    }

    function renderParticipants() {
        if (!participantListNode) {
            return;
        }

        const participants = Array.isArray(state.recentParticipants)
            ? state.recentParticipants
            : [];

        if (!participants.length) {
            const emptyItem = createElement("li", "empty-state", "No participants available yet.");
            participantListNode.replaceChildren(emptyItem);
            return;
        }

        const items = participants.map(function (participant) {
            const li = createElement("li");
            const link = createElement("a");
            link.href = buildParticipantUrl(participant.code);

            link.appendChild(createElement("span", "participant-code", participant.code));
            link.appendChild(
                createElement("span", "participant-date", formatDate(participant.createdAt))
            );

            li.appendChild(link);
            return li;
        });

        participantListNode.replaceChildren.apply(participantListNode, items);
    }

    function renderWidget() {
        const completionRate = state.totalPre
            ? Math.round((state.totalPost / state.totalPre) * 100)
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
        grid.appendChild(createStatItem("Pre Surveys", state.totalPre, "neutral"));
        grid.appendChild(createStatItem("Post Surveys", state.totalPost, "calm"));
        grid.appendChild(createStatItem("Cards Issued", state.cardsIssued, "warm"));
        grid.appendChild(createStatItem("Participants", state.participants, "neutral"));
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
    }

    function applyServerState(nextState) {
        state = Object.assign({}, state, nextState || {});
        renderWidget();
        renderParticipants();
    }

    async function refreshLiveData() {
        if (!state.summaryUrl) {
            return;
        }

        try {
            const response = await fetch(state.summaryUrl, {
                credentials: "same-origin",
                headers: {
                    Accept: "application/json",
                },
            });

            if (!response.ok) {
                return;
            }

            const payload = await response.json();
            applyServerState(payload);
        } catch (error) {
            console.error("Live dashboard refresh failed", error);
        }
    }

    applyServerState(state);
    window.setInterval(refreshLiveData, 5000);
})();
