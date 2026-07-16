// Live character counters. Any element with data-char-counter-for="<id>"
// mirrors the length of the referenced input/textarea into its own
// textContent as "<used>/<max>" (max read from the target's maxlength
// attribute). Safe to include on any page: no-op wherever no such
// element exists.
document.addEventListener("DOMContentLoaded", () => {
    const counters = document.querySelectorAll("[data-char-counter-for]");

    counters.forEach((counter) => {
        const target = document.getElementById(counter.getAttribute("data-char-counter-for"));
        if (!target) {
            return;
        }

        const max = target.getAttribute("maxlength");

        function render() {
            counter.textContent = max ? `${target.value.length}/${max}` : `${target.value.length}`;
        }

        target.addEventListener("input", render);
        render();
    });
});
