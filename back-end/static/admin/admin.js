// Admin panel client JS. Externalized (not inline) so the admin pages can ship a
// strict Content-Security-Policy with script-src 'self' (no 'unsafe-inline').
(function () {
  "use strict";

  // Stateless double-submit CSRF: echo the admin-session csrf secret on every
  // htmx request as the X-CSRF-Token header (the server compares it to the
  // signed, httponly cookie claim).
  document.addEventListener("htmx:configRequest", function (evt) {
    var meta = document.querySelector('meta[name="csrf-token"]');
    if (meta && meta.content) evt.detail.headers["X-CSRF-Token"] = meta.content;
  });

  // Surface admin-API JSON responses (htmx swaps HTML, so messages — e.g. the
  // one-time temp password — would otherwise be invisible).
  document.addEventListener("htmx:afterRequest", function (evt) {
    var xhr = evt.detail.xhr;
    if (!xhr) return;
    var ct = xhr.getResponseHeader("Content-Type") || "";
    if (ct.indexOf("application/json") === -1) return;
    var data;
    try {
      data = JSON.parse(xhr.responseText);
    } catch (e) {
      return;
    }
    if (data.temp_password) {
      flash(
        (data.message ? data.message + " " : "") + "Temporary password: " + data.temp_password,
        "ok",
        true
      );
    } else if (data.message) {
      flash(data.message, data.status === "error" ? "err" : "ok");
    }
  });

  // SECURITY: messages embed user-controlled data (emails, org names). Render
  // with textContent, NEVER innerHTML, so they can't inject markup/script.
  function flash(msg, kind, sticky) {
    var el = document.getElementById("flash");
    if (!el) return;
    el.textContent = "";
    var div = document.createElement("div");
    div.className = "flash " + (kind || "ok");
    div.textContent = msg;
    if (sticky) {
      var btn = document.createElement("button");
      btn.type = "button";
      btn.textContent = "dismiss";
      btn.addEventListener("click", function () {
        div.remove();
      });
      div.appendChild(document.createTextNode(" "));
      div.appendChild(btn);
    } else {
      setTimeout(function () {
        el.textContent = "";
      }, 4000);
    }
    el.appendChild(div);
  }
  window.flash = flash;
})();
