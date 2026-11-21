for (const button of document.querySelectorAll("[data-copy]")) {
    if (!navigator.clipboard) continue;
    button.hidden = false;
    button.addEventListener("click", async () => {
        try {
            await navigator.clipboard.writeText(button.dataset.copy);
            button.textContent = "Copied";
        } catch {
            const range = document.createRange();
            range.selectNodeContents(button.parentElement.querySelector("code"));
            const selection = window.getSelection();
            selection.removeAllRanges();
            selection.addRange(range);
            button.textContent = "Selected";
        }
    });
}
const form = document.querySelector("form[role=search]");
if (form) {
    const input = document.getElementById("query");
    const entries = Array.from(document.querySelectorAll(".entry"));
    const filters = Array.from(document.querySelectorAll("[data-filter]"));
    const pager = document.querySelector(".pager");
    const previous = document.getElementById("previous");
    const next = document.getElementById("next");
    const perPage = 18;
    let kind = "all";
    let number = 1;
    function paint(sync) {
        const tokens = input.value.toLowerCase().trim().split(/\s+/).filter(Boolean);
        const matches = entries.filter(entry => (kind === "all" || entry.dataset.kind === kind)
            && tokens.every(word => entry.dataset.search.includes(word)));
        const count = Math.ceil(matches.length / perPage);
        number = Math.max(1, Math.min(number, count || 1));
        const visible = new Set(matches.slice((number - 1) * perPage, number * perPage));
        entries.forEach(entry => { entry.hidden = !visible.has(entry); });
        for (const f of filters) f.setAttribute("aria-current", String(f.dataset.filter === kind));
        document.getElementById("empty").hidden = matches.length > 0;
        document.getElementById("status").textContent = matches.length + " matching entries";
        document.getElementById("page-number").textContent = "Page " + number + " of " + count;
        previous.disabled = number <= 1;
        next.disabled = number >= count;
        pager.hidden = count <= 1;
        if (sync) {
            const url = new URL(location.href);
            for (const [key, value] of Object.entries({q:input.value.trim(), kind:kind === "all" ? "" : kind, page:number > 1 ? String(number) : ""})) {
                if (value) url.searchParams.set(key, value);
                else url.searchParams.delete(key);
            }
            history.replaceState(null, "", url);
        }
    }
    function read() {
        const params = new URL(location.href).searchParams;
        input.value = params.get("q") || "";
        const selected = params.get("kind");
        kind = filters.some(f => f.dataset.filter === selected) ? selected : "all";
        number = Number.parseInt(params.get("page") || "1", 10) || 1;
        paint(false);
    }
    input.addEventListener("input", () => { number = 1; paint(true); });
    form.addEventListener("submit", event => { event.preventDefault(); number=1; paint(true); });
    for (const filter of filters) filter.addEventListener("click", event => {
        if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
        event.preventDefault(); kind=filter.dataset.filter; number=1; paint(true);
    });
    function flip(delta) {
        number += delta; paint(true);
        document.getElementById("browse").scrollIntoView({block:"start"});
    }
    previous.addEventListener("click", () => flip(-1));
    next.addEventListener("click", () => flip(1));
    window.addEventListener("popstate",read);
    read();
}
