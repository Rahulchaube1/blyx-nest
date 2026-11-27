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
    const container = document.getElementById("entries");
    const initial = [...container.children];
    const filters = [...document.querySelectorAll("[data-filter]")];
    const previous = document.getElementById("previous");
    const next = document.getElementById("next");
    const pageText = document.getElementById("page-number");
    const firstPageText = pageText.textContent;
    const kinds = new Set(filters.map(f => f.dataset.filter));
    const perPage = 18;
    let request;
    let generation = 0;
    let kind, number;

    function catalog() {
        if (!request) {
            request = import("./nest-sdk.mjs").then(async ({NestClient}) => {
                const rows = await new NestClient(document.baseURI).catalog();
                return rows.map(p => ({...p, search: [p.slug, p.title, p.description, p.kind].join(" ").toLowerCase()}));
            }).catch(error => { request = undefined; throw error; });
        }
        return request;
    }

    function card(p) {
        const article = initial[0].cloneNode(true);
        article.removeAttribute("data-search");
        article.dataset.kind = p.kind;
        article.querySelector("a").href = (p.kind === "tool" ? "tools/" : "packages/") + p.slug + ".html";
        article.querySelector("img").src = p.icon;
        const meta = article.querySelector(".entry-meta");
        meta.firstChild.textContent = p.kind[0].toUpperCase() + p.kind.slice(1);
        meta.querySelector("span").textContent = "v" + p.latest;
        article.querySelector("h3").textContent = p.title;
        article.querySelector("p").textContent = p.description;
        return article;
    }

    async function paint(sync) {
        const revision = ++generation;
        const q = input.value.trim().toLowerCase();
        document.getElementById("load-error").hidden = true;
        for (const item of filters) item.setAttribute("aria-current", String(item.dataset.filter === kind));
        if (!q && kind === "all" && number === 1 && !request) {
            container.replaceChildren(...initial);
            pageText.textContent = firstPageText;
            previous.disabled = true;
        } else {
            try {
                const rows = await catalog();
                if (revision !== generation) return;
                const words = q.split(/\s+/).filter(Boolean);
                const matches = rows.filter(p => (kind === "all" || kind === p.kind) && words.every(w => p.search.includes(w)));
                const pages = Math.ceil(matches.length / perPage);
                number = Math.min(number, pages || 1);
                const visible = matches.slice((number - 1) * perPage, number * perPage);
                container.replaceChildren(...visible.map(card));
                document.getElementById("empty").hidden = !!matches.length;
                document.getElementById("status").textContent = matches.length + " matching entries";
                pageText.textContent = "Page " + number + " of " + pages;
                previous.disabled = number <= 1;
                next.disabled = number >= pages;
                document.querySelector(".pager").hidden = pages <= 1;
            } catch {
                if (revision === generation) document.getElementById("load-error").hidden = false;
                return;
            }
        }
        if (sync) {
            const url = new URL(location.href);
            for (const [key,value] of Object.entries({q:input.value.trim(),kind:kind === "all" ? "" : kind,page:number > 1 ? String(number) : ""})) {
                if (value) url.searchParams.set(key,value); else url.searchParams.delete(key);
            }
            history.replaceState(null, "", url);
        }
    }
    function read() {
        const params = new URL(location.href).searchParams;
        input.value = params.get("q") || "";
        kind = kinds.has(params.get("kind")) ? params.get("kind") : "all";
        number = Math.max(1, Number.parseInt(params.get("page"),10) || 1);
        paint(false);
    }
    input.addEventListener("input", () => {number=1; paint(true);});
    form.addEventListener("submit", event => {event.preventDefault(); number=1; paint(true);});
    for (const filter of filters) filter.addEventListener("click", event => {
        if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
        event.preventDefault(); kind=filter.dataset.filter; number=1; paint(true);
    });
    function flip(delta) {
        number+=delta; paint(true);
        document.getElementById("browse").scrollIntoView({block:"start"});
    }
    previous.addEventListener("click", () => flip(-1));
    next.addEventListener("click", () => flip(1));
    document.getElementById("retry-search").addEventListener("click", () => paint(true));
    window.addEventListener("popstate",read);
    read();
}

const snapshot = document.getElementById("snapshot");
const strip = document.querySelector("[data-release-stamp]");
if (strip) {
    async function checkSnapshot() {
        if (document.hidden) return;
        try {
            const response = await fetch("api/v1/stats.json", {cache:"no-cache", signal: AbortSignal.timeout(10000)});
            if (!response.ok) return;
            const data = await response.json();
            if (data.schema === 1 && data.publishedAt > strip.dataset.releaseStamp) {
                const counts = Object.entries(data.fileTypes).sort((a,b) => b[1] - a[1]);
                const bars = counts.map(([type,count]) => {
                    const row = document.createElement("li");
                    const label = document.createElement("span");
                    label.textContent = type;
                    const meter = document.createElement("meter");
                    meter.max = counts[0][1];
                    meter.value = count;
                    const value = document.createElement("strong");
                    value.textContent = count.toLocaleString();
                    row.append(label,meter,value);
                    return row;
                });
                document.querySelector(".file-bars")?.replaceChildren(...bars);
                for (const el of document.querySelectorAll("[data-metric]")) {
                    el.textContent = data[el.dataset.metric].toLocaleString();
                }
                strip.dataset.releaseStamp = data.publishedAt;
                if (snapshot) snapshot.querySelector("time").textContent = data.publishedAt;
            }
        } catch { /* The published snapshot stays readable offline. */ }
    }
    const active = document.getElementById("active-browsers");
    async function checkActivity() {
        try {
            const r = await fetch("https://www.blyx-lang.space/api/playground/activity", {cache: "no-store", credentials: "omit", signal: AbortSignal.timeout(10000)});
            if (!r.ok) throw new Error();
            const {active: count, observed} = await r.json();
            const age = Date.now() - Date.parse(observed);
            if (!Number.isSafeInteger(count) || count < 0 || !(age >= -60000 && age < 180000)) throw new Error();
            active.textContent = count.toLocaleString();
            active.removeAttribute("aria-label");
            active.title = "Observed " + observed;
        } catch {
            active.textContent = "Unavailable";
            active.removeAttribute("aria-label");
            active.title = "A recent playground sample could not be retrieved.";
        }
    }
    let checking = false;
    async function refresh() {
        if (document.hidden || checking) return;
        checking = true;
        try { await Promise.all([checkSnapshot(), checkActivity()]); }
        finally { checking = false; }
    }
    refresh();
    setInterval(refresh, 60000);
    document.addEventListener("visibilitychange", refresh);
}
