
(function () {
  const btn = document.querySelector(".menu-btn");
  const header = document.querySelector(".site-header");
  if (btn && header) {
    btn.addEventListener("click", () => {
      const open = header.classList.toggle("open");
      btn.setAttribute("aria-expanded", open ? "true" : "false");
    });
  }
  const form = document.querySelector("form[data-contact]");
  if (form) {
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const btn = form.querySelector("button[type=submit]");
      if (btn) { btn.disabled = true; btn.textContent = "Sending…"; }
      const data = Object.fromEntries(new FormData(form).entries());
      data.trades = [...form.querySelectorAll("input[name=trades]:checked")].map((i) => i.value).join(", ");
      try {
        const first = (data.first || "").trim();
        const last = (data.last || "").trim();
        const email = (data.email || "").trim();
        const name = (first + " " + last).trim() || "Website visitor";
        const message = [
          "From: " + name,
          "Email: " + email,
          "Phone: " + ((data.phone || "").trim() || "—"),
          "Company / GC: " + ((data.company || "").trim() || "—"),
          "Project: " + ((data.project || "").trim() || "—"),
          "City / site: " + ((data.location || "").trim() || "—"),
          "Bid due: " + ((data.bid_due || "").trim() || "—"),
          "Trades: " + ((data.trades || "").trim() || "—"),
          "",
          (data.help || "").trim(),
        ].join("\n");
        const payload = {
          name,
          email,
          _replyto: email,
          _subject: "Bid request: " + ((data.project || "").trim() || name),
          message,
          _captcha: "false",
        };
        let out = null;
        let okSend = false;
        try {
          const res = await fetch("/api/contact", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(data),
          });
          out = await res.json();
          okSend = res.ok && out && out.ok;
        } catch (_) { /* static host has no /api */ }
        if (!okSend) {
          const res = await fetch("https://formsubmit.co/ajax/info@ledfordllc.com", {
            method: "POST",
            headers: { "Content-Type": "application/json", "Accept": "application/json" },
            body: JSON.stringify(payload),
          });
          out = await res.json().catch(() => ({}));
          if (!res.ok) throw new Error((out && out.message) || "Send failed");
        }
        form.hidden = true;
        const ok = document.querySelector(".success");
        if (ok) ok.style.display = "block";
      } catch (err) {
        if (btn) { btn.disabled = false; btn.textContent = "Send bid request"; }
        alert("Could not send just now. Email info@ledfordllc.com directly.");
      }
    });
  }

  const gallery = document.querySelector("[data-gallery]");
  if (!gallery) return;

  const drop = document.querySelector("[data-dropzone]");
  const fileInput = document.querySelector("[data-file-input]");

  function itemName(item) {
    return typeof item === "string" ? item : item.name;
  }

  async function saveCaption(name, caption) {
    await fetch("/api/caption", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ file: name, caption }),
    });
  }

  async function loadGallery() {
    let files = [];
    try {
      const res = await fetch("/api/projects", { cache: "no-store" });
      if (res.ok) files = await res.json();
    } catch (_) { files = []; }
    gallery.innerHTML = "";
    files.forEach((item, i) => {
      const name = itemName(item);
      const caption = typeof item === "string" ? "" : (item.caption || "");
      const fig = document.createElement("figure");
      if (i % 7 === 0) fig.classList.add("wide");
      const img = document.createElement("img");
      img.src = "images/projects/" + encodeURIComponent(name);
      img.alt = caption || "Project photo";
      fig.append(img);
      if (drop) {
        const rm = document.createElement("button");
        rm.type = "button";
        rm.className = "remove";
        rm.setAttribute("aria-label", "Remove photo");
        rm.textContent = "×";
        rm.addEventListener("click", async (e) => {
          e.preventDefault();
          e.stopPropagation();
          await fetch("/api/projects/" + encodeURIComponent(name), { method: "DELETE" });
          loadGallery();
        });
        fig.append(rm);
        const field = document.createElement("textarea");
        field.className = "caption-input";
        field.rows = 2;
        field.maxLength = 280;
        field.placeholder = "Short description. Job, city, or trade.";
        field.value = caption;
        let timer;
        const persist = () => saveCaption(name, field.value.trim());
        field.addEventListener("input", () => {
          clearTimeout(timer);
          timer = setTimeout(persist, 400);
        });
        field.addEventListener("blur", persist);
        fig.append(field);
      } else if (caption) {
        const cap = document.createElement("figcaption");
        cap.textContent = caption;
        fig.append(cap);
      }
      gallery.append(fig);
    });
  }

  async function upload(files) {
    if (!files || !files.length) return;
    const data = new FormData();
    [...files].forEach((f) => data.append("files", f));
    await fetch("/api/projects", { method: "POST", body: data });
    if (fileInput) fileInput.value = "";
    loadGallery();
  }

  if (drop && fileInput) {
    drop.addEventListener("click", () => fileInput.click());
    drop.addEventListener("dragover", (e) => {
      e.preventDefault();
      drop.classList.add("drag");
    });
    drop.addEventListener("dragleave", () => drop.classList.remove("drag"));
    drop.addEventListener("drop", (e) => {
      e.preventDefault();
      drop.classList.remove("drag");
      upload(e.dataTransfer.files);
    });
    fileInput.addEventListener("change", () => upload(fileInput.files));
  }

  loadGallery();
})();
