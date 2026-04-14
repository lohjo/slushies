(function () {
    const mountNode = document.getElementById("react-dashboard-widget");
    const payloadNode = document.getElementById("dashboard-stats-data");

    if (!mountNode || !payloadNode || !window.React || !window.ReactDOM) {
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

    const { createElement: h, useMemo } = React;

    function StatItem({ label, value, tone }) {
        return h(
            "article",
            { className: "stat-item stat-" + tone },
            h("p", { className: "stat-label" }, label),
            h("p", { className: "stat-value" }, String(value))
        );
    }

    function EditorialDashboardWidget(props) {
        const completionRate = useMemo(function () {
            if (!props.totalPre) {
                return 0;
            }
            return Math.round((props.totalPost / props.totalPre) * 100);
        }, [props.totalPost, props.totalPre]);

        return h(
            "section",
            { className: "editorial-widget" },
            h(
                "div",
                { className: "widget-intro" },
                h("p", { className: "widget-kicker" }, "Live Snapshot"),
                h("h2", null, "Response Momentum"),
                h(
                    "p",
                    { className: "widget-copy" },
                    "A concise pulse-check on survey completion and card delivery."
                )
            ),
            h(
                "div",
                { className: "widget-grid" },
                h(StatItem, { label: "Pre Surveys", value: props.totalPre, tone: "neutral" }),
                h(StatItem, { label: "Post Surveys", value: props.totalPost, tone: "calm" }),
                h(StatItem, { label: "Cards Issued", value: props.cardsIssued, tone: "warm" }),
                h(StatItem, { label: "Participants", value: props.participants, tone: "neutral" })
            ),
            h(
                "div",
                { className: "completion-band" },
                h("p", null, "Completion Rate"),
                h("strong", null, completionRate + "%"),
                h(
                    "div",
                    {
                        className: "completion-meter",
                        role: "progressbar",
                        "aria-valuemin": 0,
                        "aria-valuemax": 100,
                        "aria-valuenow": completionRate,
                        "aria-label": "Post survey completion rate",
                    },
                    h("span", { style: { width: Math.max(0, Math.min(completionRate, 100)) + "%" } })
                )
            )
        );
    }

    ReactDOM.createRoot(mountNode).render(h(EditorialDashboardWidget, data));
})();
