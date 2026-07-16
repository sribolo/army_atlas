// Any [data-back-link] anchor has a fixed href as its fallback destination,
// but there are often multiple valid entry points to the page it sits on
// (a memory can be reached from the feed, search, a profile, a concert
// page, ...). Prefer real browser history so "back" returns to wherever
// the user actually came from; only fall back to the fixed href when
// there's no same-origin history to go back to (e.g. a direct link).
document.addEventListener("DOMContentLoaded", () => {
    const links = document.querySelectorAll("[data-back-link]");
    if (links.length === 0) {
        return;
    }

    let cameFromSameOrigin = false;
    try {
        cameFromSameOrigin = Boolean(document.referrer) && new URL(document.referrer).origin === window.location.origin;
    } catch (error) {
        cameFromSameOrigin = false;
    }

    if (!cameFromSameOrigin || window.history.length <= 1) {
        return;
    }

    links.forEach((link) => {
        link.addEventListener("click", (event) => {
            event.preventDefault();
            window.history.back();
        });
    });
});
