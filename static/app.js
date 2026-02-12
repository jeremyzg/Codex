const api = async (url, method = "GET", body = null) => {
  const res = await fetch(url, {
    method,
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || "Request failed");
  return data;
};

const formToObject = (form) => Object.fromEntries(new FormData(form).entries());

const statusEl = document.getElementById("professional-status");
const recContainer = document.getElementById("recommendations");
const dashboardEl = document.getElementById("dashboard");

function toast(msg, isError = false) {
  statusEl.textContent = msg;
  statusEl.className = isError ? "status error" : "status";
}

document.getElementById("professional-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const payload = formToObject(e.target);
  try {
    const saved = await api("/api/professionals", "POST", payload);
    toast(`Saved. Professional ID: ${saved.id}`);
  } catch (err) {
    toast(err.message, true);
  }
});

document.getElementById("client-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const payload = formToObject(e.target);
  payload.professional_id = Number(payload.professional_id);
  payload.budget = Number(payload.budget);
  try {
    const added = await api("/api/clients", "POST", payload);
    alert(`Client added. Client ID: ${added.id}`);
    e.target.reset();
  } catch (err) {
    alert(err.message);
  }
});

document.getElementById("add-occasion-btn").addEventListener("click", async () => {
  const clientId = Number(document.getElementById("occasion-client-id").value);
  const name = document.getElementById("occasion-name").value.trim();
  const date = document.getElementById("occasion-date").value;
  if (!clientId || !name || !date) {
    alert("Client ID, occasion name, and date are required.");
    return;
  }
  try {
    await api(`/api/clients/${clientId}/occasions`, "POST", { name, date });
    alert("Occasion saved.");
  } catch (err) {
    alert(err.message);
  }
});

document.getElementById("load-recs-btn").addEventListener("click", async () => {
  const clientId = Number(document.getElementById("rec-client-id").value);
  const occasion = document.getElementById("rec-occasion").value || "birthday";
  if (!clientId) {
    recContainer.textContent = "Please enter a client ID.";
    return;
  }
  recContainer.textContent = "Loading recommendations...";

  try {
    const recs = await api(`/api/clients/${clientId}/recommendations?occasion=${encodeURIComponent(occasion)}&limit=10`);
    if (!recs.length) {
      recContainer.textContent = "No recommendations found.";
      return;
    }
    recContainer.innerHTML = "";

    recs.forEach((rec) => {
      const div = document.createElement("div");
      div.className = "rec-card";
      div.innerHTML = `
        <strong>${rec.product_name}</strong>
        <p>${rec.vendor} · ${rec.category} · $${Number(rec.price).toFixed(2)}</p>
        <small>${rec.reason}</small><br/>
        <a href="${rec.link}" target="_blank" rel="noreferrer">Open vendor</a>
        <div><button class="order-btn">Confirm Order</button></div>
      `;

      div.querySelector(".order-btn").addEventListener("click", async () => {
        try {
          await api("/api/orders", "POST", {
            client_id: clientId,
            occasion_name: occasion,
            vendor: rec.vendor,
            product_name: rec.product_name,
            price: rec.price,
          });
          alert("Order confirmed.");
        } catch (err) {
          alert(err.message);
        }
      });

      recContainer.appendChild(div);
    });
  } catch (err) {
    recContainer.textContent = err.message;
  }
});

document.getElementById("refresh-dashboard").addEventListener("click", async () => {
  try {
    const dashboard = await api("/api/dashboard");
    dashboardEl.textContent = JSON.stringify(dashboard, null, 2);
  } catch (err) {
    dashboardEl.textContent = err.message;
  }
});
