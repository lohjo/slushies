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

    // FIX: Track whether participant list was already populated server-side.
    // Only allow JS to update the list after a full-data poll response.
    // Prevents poll (limit=50) from replacing a larger server-rendered list.
    let participantListPopulatedByServer = (state.recentParticipants || []).length > 0;

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
            // FIX: Don't wipe the server-rendered list if poll returns empty.
            // Empty can mean the request failed or poll ran before DB populated.
            // Only render empty state if we never had server-side data either.
            if (!participantListPopulatedByServer) {
                const emptyItem = createElement("li", "empty-state", "No participants available yet.");
                participantListNode.replaceChildren(emptyItem);
            }
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
        // Once JS has rendered the list from real data, allow future updates
        participantListPopulatedByServer = true;
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
                // Session expired or server error — stop polling silently.
                // Don't wipe the existing UI.
                return;
            }

            const payload = await response.json();

            // FIX: Only update participant list from poll if poll returned data.
            // Avoids limit-50 poll replacing a server-rendered list of 200+ participants.
            // Stats (counters) always update from poll. List only updates when non-empty.
            if (!payload.recentParticipants || payload.recentParticipants.length === 0) {
                // Keep current list; only update counters
                const statsOnly = {
                    totalPre: payload.totalPre,
                    totalPost: payload.totalPost,
                    cardsIssued: payload.cardsIssued,
                    participants: payload.participants,
                    recentParticipants: state.recentParticipants,
                };
                applyServerState(statsOnly);
            } else {
                applyServerState(payload);
            }
        } catch (error) {
            console.error("Live dashboard refresh failed", error);
        }
    }

    applyServerState(state);

    // FIX: Use visibilitychange to pause polling when tab hidden.
    // Reduces unnecessary requests and prevents stale-data overwrites on refocus.
    let pollInterval = window.setInterval(refreshLiveData, 5000);

    document.addEventListener("visibilitychange", function () {
        if (document.hidden) {
            window.clearInterval(pollInterval);
        } else {
            refreshLiveData(); // immediate refresh on tab focus
            pollInterval = window.setInterval(refreshLiveData, 5000);
        }
    });
})();