const statusEl = document.getElementById("status");
const secondsEl = document.getElementById("seconds");

function setStatus(text) {
    statusEl.textContent = text;
}

async function post(url, body) {
    try {
        const res = await fetch(url, {
            method: "POST",
            headers: body ? { "Content-Type": "application/json" } : undefined,
            body: body ? JSON.stringify(body) : undefined,
        });
        const data = await res.json().catch(() => null);
        if (!res.ok) {
            setStatus(`Erro: ${data?.detail ?? res.status}`);
            return;
        }
        setStatus("OK");
    } catch (err) {
        setStatus("Falha ao conectar com a API");
    }
}

document.querySelectorAll(".btn[data-part]").forEach((btn) => {
    btn.addEventListener("click", () => {
        post("/api/move", {
            part: btn.dataset.part,
            direction: btn.dataset.direction,
            seconds: parseFloat(secondsEl.value) || 0,
        });
    });
});

document.getElementById("stop-btn").addEventListener("click", () => post("/api/stop"));

document.querySelectorAll("[data-memory-save]").forEach((btn) => {
    btn.addEventListener("click", () => post(`/api/memory/save/${btn.dataset.memorySave}`));
});

document.querySelectorAll("[data-memory-recall]").forEach((btn) => {
    btn.addEventListener("click", () => post(`/api/memory/recall/${btn.dataset.memoryRecall}`));
});
