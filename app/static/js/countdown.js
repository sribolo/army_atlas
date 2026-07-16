// Client-side countdown timers. There is no Countdown model — every
// timer on the page reads its target straight from a
// data-countdown-target attribute (a UTC ISO 8601 string with an explicit
// offset, e.g. Concert.starts_at_utc_iso) and updates once a second. Safe
// to include on any page: it's a no-op wherever no such attribute exists.
//
// Two render modes, chosen per-element:
//   - Plain text: `<span data-countdown-target="...">` gets its
//     textContent set to "Xd Xh Xm Xs".
//   - Split boxes (the aa-ticket-style D/H/M/S cards): a container with
//     data-countdown-target holding descendants tagged
//     data-countdown-unit="d|h|m|s" gets each unit's textContent updated
//     individually instead, so the numbers can be styled as separate tiles.
document.addEventListener("DOMContentLoaded", () => {
    const elements = document.querySelectorAll("[data-countdown-target]");
    if (elements.length === 0) {
        return;
    }

    function render() {
        const now = Date.now();
        elements.forEach((el) => {
            const target = new Date(el.dataset.countdownTarget).getTime();
            const diff = target - now;
            const units = el.querySelectorAll("[data-countdown-unit]");

            if (diff <= 0) {
                if (units.length > 0) {
                    units.forEach((u) => { u.textContent = "0"; });
                } else {
                    el.textContent = "Happening now!";
                }
                return;
            }

            const days = Math.floor(diff / 86400000);
            const hours = Math.floor((diff / 3600000) % 24);
            const minutes = Math.floor((diff / 60000) % 60);
            const seconds = Math.floor((diff / 1000) % 60);

            if (units.length > 0) {
                units.forEach((u) => {
                    const value = { d: days, h: hours, m: minutes, s: seconds }[u.dataset.countdownUnit];
                    if (value !== undefined) u.textContent = value;
                });
            } else {
                el.textContent = `${days}d ${hours}h ${minutes}m ${seconds}s`;
            }
        });
    }

    render();
    setInterval(render, 1000);
});